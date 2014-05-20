import os
import sys
if sys.version < (2, 6):
    from distutils.command import register

    def isstr((k, v)):
        return isinstance(v, basestring)

    def patch(func):
        def post_to_server(self, data, auth=None):
            for key, value in filter(isstr, data.items()):
                data[key] = value.decode('utf8')
            return func(self, data, auth)
        return post_to_server

    register.register.post_to_server = patch(register.register.post_to_server)

from setuptools import setup
import pgpagecache

def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()


setup(name='pgpagecache',
      version=pgpagecache.__version__,
      author='Chrysostomos Nanakos',
      author_email='chris@include.gr',
      description='PostgreSQL objects resident in OS memory',
      long_description=read('README'),
      license='GPL',
      keywords='PostgreSQL postgres pagecache linux cache buffercache buffer memory',
      platforms=['posix'],
      packages=['pgpagecache'],
      install_requires=['tabulate', 'psycopg2'],
      entry_points = {
          'console_scripts': [
              'pgpagecache = pgpagecache.pgpagecache:main'
          ],
      },
      classifiers=[
          'Environment :: Console',
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
          'Operating System :: POSIX :: Linux',
          'Topic :: Utilities',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
      ],
     )
