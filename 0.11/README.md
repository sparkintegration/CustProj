CustProj
========

A plugin to manage customers and projects in concert with the TracLogs plugin

Installation
------------

Initial database must be created with the "setup.sql" file (i.e. sqlite3 <trac env>/db/trac.db < customers.sql).  After this, the usual Trac database upgrade process can be used (i.e. trac-admin <trac env> upgrade).
    
    
If your installation is not located at http://host/trac, htodcs/js/cust.js must be edited so that the getJSON call contains the correct URL.