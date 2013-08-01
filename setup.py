from setuptools import setup, find_packages
import os

version = '0.1'

setup(name='upiqsite.projects',
      version=version,
      description="Policy product for projects.upiq.org site, customizing QI Teamspace and Plone 4.",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      classifiers=[
        "Framework :: Plone",
        "Programming Language :: Python",
        ],
      keywords='',
      author='Sean Upton',
      author_email='sean.upton@hsc.utah.edu',
      url='http://launchpad.net/upiq',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['upiqsite'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'uu.qiext',
          'uu.formlibrary',
          'uu.smartdate',
          'Solgema.fullcalendar',
          'uu.inviting',
          'uu.staticmap',
          'uu.chart',
          'uu.eventintegration',
          'Products.qi',
          'Products.CMFPlone',
          'plone.browserlayer',
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-

      [z3c.autoinclude.plugin]
      target = plone
      """,
      )
