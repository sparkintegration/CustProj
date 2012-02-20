"""
SetupCustomerProjects:
plugin to enable the environment for CustomerProjects.
This plugin must be initialized prior to using CustomerProjects
"""

from api import custom_fields

from trac.core import *
from trac.db import Table, Column, Index, DatabaseManager
from trac.env import IEnvironmentSetupParticipant

from tracsqlhelper import *


class SetupCustomerProjects(Component):

    implements(IEnvironmentSetupParticipant)

    ### methods for IEnvironmentSetupParticipant

    """Extension point interface for components that need to participate in the
    creation and upgrading of Trac environments, for example to create
    additional database tables."""
        

    def environment_created(self):
        """Called when a new Trac environment is created."""
        if self.environment_needs_upgrade(None):
            self.upgrade_environment(None)

    def environment_needs_upgrade(self, db):
        """Called when Trac checks whether the environment needs to be upgraded.
        
        Should return `True` if this participant needs an upgrade to be
        performed, `False` otherwise.
        """
        version = self.version()
        return version < len(self.steps)

    def upgrade_environment(self, db):
        """Actually perform an environment upgrade.
        
        Implementations of this method should not commit any database
        transactions. This is done implicitly after all participants have
        performed the upgrades they need without an error being raised.
        """
        if not self.environment_needs_upgrade(db):
            return

        version = self.version()
        for version in range(self.version(), len(self.steps)):
            for step in self.steps[version]:
                step(self)
        execute_non_query(self.env, "insert into system (name, value) values ('customerProjects.db_version', '%s');" % len(self.steps))

    ### helper methods

    def version(self):
        """returns version of the database (an int)"""
        version = get_scalar(self.env, "select value from system where name = 'customerProjects.db_version';")
        if version:
            return int(version)
        return 0


    ### upgrade steps

    def create_db(self):

        customers_table = Table('customers', key=('id'))[
            Column('id', auto_increment=True),
            Column('name'),
            Column('data'),
            Index(['id'])]

        c_projects_table = Table('c_projects', key=('id'))[
            Column('id', auto_increment=True),
            Column('parentId', type='int'),
            Column('customerId',type='int'),
            Column('name'),
            Column('data'),
            Column('budget', type='int', default='0'),
            Column('active', type='bool', default='1'),
            Column('workon', type='bool', default='1'),
            Index(['id'])]

        create_table(self.env, customers_table)
        create_table(self.env, c_projects_table)
        execute_non_query(self.env, "insert into system (name, value) values ('customerProjects.db_version', '1');")

    def update_custom_fields(self):
        ticket_custom = 'ticket-custom'
        for name in custom_fields:
            field = custom_fields[name].copy() 
            field_type = field.pop('type', 'text')
            if not self.config.get(ticket_custom, field_type):
                self.config.set(ticket_custom, name, field_type)
            for key, value in field.items():
                self.config.set(ticket_custom, '%s.%s' % (name, key), value)
        self.config.save()

    def create_custom_fields(self):
        section = "customerProjects"
        if not self.config.get(section,'defaultCustomer'):
            self.config.set(section,'defaultCustomer','0')
        if not self.config.get(section,'defaultProject'):
            self.config.set(section,'defaultProject','0')
        if not self.config.get(section,'awayProject'):
            self.config.set(section,'awayProject','0')
        self.config.save()

    def initialize_old_tickets(self):
        execute_non_query(self.env, """INSERT INTO ticket_custom (ticket, name, value)
  SELECT id, 'project', '0' FROM ticket WHERE id NOT IN (
    SELECT ticket from ticket_custom WHERE name='project'
  );
""")

         
    # ordered steps for upgrading - removed create_db
    steps = [ [ update_custom_fields ], # version 1
              [ initialize_old_tickets ], # version 2
              [ create_custom_fields ], # version 3
            ]
