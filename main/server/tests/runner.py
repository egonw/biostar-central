"""
Main test script is executed when running::

    biostar.sh test"

"""
import sys, os, django

if django.VERSION < (1, 3):
    print '*** Django version 1.3 or higher required.'
    print '*** Your version is %s' % '.'.join( map(str, django.VERSION))
    sys.exit()

from django.utils import unittest
from django.test.simple import DjangoTestSuiteRunner
from coverage import coverage

# add our own testing suites
#from biostar.server import html
#from biostar.tests import functional, access, voting

class BiostarTest(DjangoTestSuiteRunner):

    def __init__(self, verbosity=1, interactive=True, failfast=True, **kwargs):
        super( BiostarTest, self ).__init__(verbosity, interactive, failfast, **kwargs)

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        # add new tests then delegate to supercalss
        
        extra_tests = [
            #voting.suite(), html.suite(), access.suite(), functional.suite(), 
        ]

        if coverage:
            cov = coverage(include = [ 'main/*' ], omit=[ 'main/server/tests/*' ] )
            cov.start()
            code = super( BiostarTest, self ).run_tests(test_labels, extra_tests, **kwargs)
            cov.stop()
            if code == 0:
                # reporting if there are not errors
                cov.report()
                cov.html_report(directory="report")
                cov.xml_report()
        else:
            super( BiostarTest, self ).run_tests(test_labels, extra_tests, **kwargs)


