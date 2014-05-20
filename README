pgpagecache
===========

pgpagecache is a Python script, showing PostgreSQL objects resident in memory.
PostgreSQL relies on OS file system cache to keep performance high and it is
pretty common not to see gains in performance for buffer cache size over about
a specific limit.
Since the OS buffer cache keeps file buffers in memory as well, there are
lots of database objects in PostgreSQL cache, OS cache, or both. This is called
double buffering.

If someone wants to examine the PostgreSQL cache, he/she can use the contrib
module pg_buffercache to map each object with it's memory footprint in cache.
But, if one wanted to examine the entire cache picture, including OS cache,
he/she has to determine whether PostgreSQL object pages are resident in memory,
for this purpose one can use pgpagecache.


Required Extension
------------------

For the PostgreSQL buffercache usage the pg_buffercache extension is needed.
You can install it from the contrib modules by simply executing the command
below:

::

    postgres=# CREATE EXTENSION pg_buffercache;
    CREATE EXTENSION

Example
-------

::

  $ pgpagecache -u postgres -p apassword -d postgres -H localhost -P 5432 \
    -b /var/lib/postgresql/9.3/main/base
    PageCache Usage
    ---------------

    DB Name    Table                    Cached Pages    Total Pages    Ratio (%)    Bytes
    ---------  ---------------------  --------------  -------------  -----------  -------
    postgres   pgbench_accounts_pkey             552            552          100  2260992
    postgres   pgbench_tellers                    18             18          100    73728
    postgres   pgbench_tellers_pkey                4              4          100    16384
    postgres   pgbench_branches                   12             12          100    49152
    postgres   pgbench_branches_pkey               4              4          100    16384

    PostgreSQL BufferCache Usage
    -----------------------------

    DB Name    Table                                         Bytes
    ---------  ---------------------------------  ----------------
    postgres   pgbench_accounts                        1.38854e+07
    postgres   pgbench_accounts_pkey                   2.2528e+06
    postgres   pgbench_history                    188416
    postgres   pg_statistic                       122880
    postgres   pg_operator                        106496
    postgres   pgbench_tellers                    106496
    postgres   pg_depend_reference_index           98304
    postgres   pg_depend                           81920
    postgres   pgbench_branches                    81920
    ...
