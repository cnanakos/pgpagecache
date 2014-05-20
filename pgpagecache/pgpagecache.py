# Copyright (C) 2014 Chrysostomos Nanakos <chris@include.gr>
#
# This file is part of pgpagecache.
#
# pgpagecache is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pgpagecache.  If not, see <http://www.gnu.org/licenses/>.

from tabulate import tabulate
import os
import math
import sys
import psycopg2
from optparse import OptionParser
from mmap import (
    MAP_SHARED,
    PROT_READ,
    PAGESIZE
)
from ctypes import (
    c_int,
    c_size_t,
    c_ubyte,
    c_void_p,
    get_errno,
    cdll,
    POINTER,
    cast
)
from ctypes.util import find_library

try:
    from ctypes import c_ssize_t
except ImportError:
    from ctypes import c_longlong
    is_64bits = sys.maxsize > 2 ** 32
    c_ssize_t = c_longlong if is_64bits else c_int


libclib = find_library("c")
if libclib is None:
    raise OSError("Could not load libc dynamic library")

libc = cdll.LoadLibrary(libclib)


class PageCache(object):
    def __init__(self):
        self.MAP_FAILED = c_void_p(-1)
        self.c_off_t = c_ssize_t
        self.mmap = libc.mmap
        self.mmap.restype = c_void_p
        self.mmap.argtypes = [c_void_p, c_size_t, c_int, c_int, self.c_off_t]
        self.munmap = libc.munmap
        self.munmap.restype = c_void_p
        self.munmap.argtypes = [c_void_p, c_size_t]
        self.mincore = libc.mincore
        self.mincore.argtypes = [c_void_p, c_size_t, POINTER(c_ubyte)]
        self.mincore.restype = c_int

    def pagecache_incore(self, filename):
        with open(filename, "r") as fd:
            stat = os.fstat(fd.fileno())
            filesize = stat.st_size
            if filesize == 0:
                return (0, 0, 0.0)
            faddr = self.mmap(0, filesize, PROT_READ, MAP_SHARED, fd.fileno(),
                              0)
            if faddr == self.MAP_FAILED:
                fd.close()
                print "Failed to mmap %s (errno: %d)" % (filename, get_errno())
                sys.exit(-1)

            vec_size = (filesize + PAGESIZE - 1) / PAGESIZE
            vec = (c_ubyte * vec_size)()
            rv = self.mincore(faddr, filesize, cast(vec, POINTER(c_ubyte)))
            if rv == -1:
                fd.close()
                print "mincore failed: 0x%x, 0x%x: %d" % (faddr, filesize,
                                                          get_errno())
                sys.exit(-1)
            cached_pages = 0
            for pageidx in xrange(len(vec)):
                if vec[pageidx] & 1:
                    cached_pages += 1
            # Clean up
            fd.close()
            if faddr:
                self.munmap(faddr, filesize)
            del stat
            del vec
            # Return cached pages, total pages, ratio
            total_pages = math.ceil(float(filesize) / PAGESIZE)
            ratio = (cached_pages / total_pages)
            return (cached_pages, int(total_pages), ratio)


class PGCache(object):
    def __init__(self, username, password, dbname, hostname, port='5432'):
        self.username = username
        self.password = password
        self.dbname = dbname
        self.hostname = hostname
        self.port = port
        self.dbs = {}
        self.pagecache = {}

    def pg_connect(self):
        conn_string = "dbname='%s' user='%s' password='%s' host='%s' port='%s'"
        self.conn = psycopg2.connect(conn_string % (self.dbname, self.username,
                                     self.password, self.hostname,
                                     self.port))
        self.cursor = self.conn.cursor()

    def find_dbbase(self):
        sql_str = "show data_directory"
        self.cursor.execute(sql_str)
        for base in self.cursor.fetchall():
            return base[0]

    def find_dbid(self):
        sql_str = ("select datname, oid from pg_database where datname='%s' "
                   "and datname not like '%%template%%'" % self.dbname)
        self.cursor.execute(sql_str)
        for db in self.cursor.fetchall():
            self.dbs[db[0]] = db[1]

    def find_oid(self, oid):
        sql_str = "select relname from pg_class where oid=%s"
        self.cursor.execute(sql_str % oid)
        for x in self.cursor.fetchall():
            return x[0]

    def check_extension(self):
        sql_str = ("select true as exists from pg_available_extensions where "
                   "name='pg_buffercache' and installed_version <> '';")
        self.cursor.execute(sql_str)
        extension_exists = self.cursor.fetchone()
        if not extension_exists:
                print "pg_buffercache extension is not installed in database '%s'." % self.dbname
                sys.exit(-1)

    def pg_buffercache(self):
        self.check_extension()
        sql_str = ("SELECT current_database(),c.relname, count(*)*8192 as "
                   "bytes FROM pg_buffercache b INNER JOIN pg_class c ON "
                   "b.relfilenode = c.relfilenode AND b.reldatabase IN "
                   "(0, (SELECT oid FROM pg_database WHERE datname = "
                   "current_database())) GROUP BY c.relname ORDER BY 3 DESC")
        self.cursor.execute(sql_str)
        pg_buffercache_table = []
        for x in self.cursor.fetchall():
            temp = []
            temp.extend([x[0], x[1], x[2]])
            pg_buffercache_table.append(temp)
        return pg_buffercache_table

    def datafiles_incore(self, basedir):
        pcache = PageCache()
        for v, i in self.dbs.iteritems():
            for datafile in os.listdir(os.path.join(basedir, str(i))):
                if datafile.isalnum():
                    rel = self.find_oid(datafile)
                    if rel is None:
                        continue
                    fullpath = os.path.join(basedir, str(i), datafile)
                    self.pagecache[v + ":" + rel] = \
                        pcache.pagecache_incore(fullpath)
        del pcache

def main():
    parser = OptionParser()
    parser.add_option("-u", "--username", dest="username", help="PostgreSQL "
                      "username", default=None)
    parser.add_option("-p", "--password", dest="password", help="PostgreSQL "
                      "password", default=None)
    parser.add_option("-d", "--dbname", dest="dbname", help="PostgreSQL "
                      "database name", default=None)
    parser.add_option("-H", "--host", dest="hostname", help="PostgreSQL "
                      "hostname", default=None)
    parser.add_option("-P", "--port", dest="port", help="PostgreSQL "
                      "port", default=None)
    parser.add_option("-b", "--basedir", dest="basedir", help="PostgreSQL "
                      "base data directory", default=None)
    parser.add_option("-s", action='store_true', dest='pgcache',default=False,
                      help='Print pagecache usage only')
    parser.add_option("-S", action='store_true',dest='postgcache',
                      default=False, help='Print PostgreSQL cache usage only')
    (options, args) = parser.parse_args()

    if options.username is None:
        print ("PostgreSQL username is missing. Use the --username or -u "
               "command line option to define it")
        sys.exit(-2)
    if options.password is None:
        print ("PostgreSQL password is missing. Use the --password or -p "
               "command line option to define it")
        sys.exit(-2)
    if options.dbname is None:
        print ("PostgreSQL dbname is missing. Use the --dbname or -d "
               "command line option to define it")
        sys.exit(-2)
    if options.hostname is None:
        print ("PostgreSQL hostname is missing. Use the --host or -H "
               "command line option to define it")
        sys.exit(-2)
    if options.port is None:
        print ("PostgreSQL port is missing. Use the --port or -P "
               "command line option to define it")
        sys.exit(-2)
    if options.basedir is None:
        print ("PostgreSQL base dir is missing. Use the --basedir or -b "
               "command line option to define it")
        sys.exit(-2)

    pg = PGCache(options.username, options.password, options.dbname,
                 options.hostname, options.port)
    pg.pg_connect()
    pg.find_dbid()
    pg.datafiles_incore(options.basedir)
    pretty_print = 0  # print both
    if options.pgcache and not options.postgcache:
        pretty_print = 1  # print pagecache only
    if not options.pgcache and options.postgcache:
        pretty_print = 2  # print postgresql only
    if pretty_print == 0 or pretty_print == 1:
        pgcache_str = "PageCache Usage"
        print pgcache_str
        print "-" * len(pgcache_str) + '\n'
        pgcache_table = []
        for v, i in pg.pagecache.iteritems():
            temp = []
            temp.append(v.split(":")[0])
            temp.append(v.split(":")[1])
            temp.extend([i[0], i[1], i[2] * 100, i[0] * PAGESIZE])
            pgcache_table.append(temp)
        print tabulate(pgcache_table,
                       headers=["DB Name", "Table", "Cached Pages",
                                "Total Pages", "Ratio (%)",
                                "Bytes"],tablefmt="orgtbl"
                       )
        print '\n'
    if pretty_print == 0 or pretty_print == 2:
        pgcache_str = "PostgreSQL BufferCache Usage"
        print pgcache_str
        print "-" * len(pgcache_str) + '\n'
        print tabulate(pg.pg_buffercache(),
                       headers=["DB Name", "Table", "Bytes"],
                       tablefmt="orgtbl")

if __name__ == "__main__":
    main()
