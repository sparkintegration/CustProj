"""
 Sidebar handlers for customerProjects
"""

from customerProjects import *

from componentdependencies.interface import IRequireComponents
from genshi.builder import tag
from genshi.filters import Transformer
from genshi.filters.transform import StreamBuffer
from ticketsidebarprovider.interface import ITicketSidebarProvider
from ticketsidebarprovider.ticketsidebar import TicketSidebarProvider
from trac.core import *
from trac.config import *
from trac.ticket import Ticket
from trac.ticket.model import Milestone
from trac.web.api import IRequestHandler
from trac.web.api import ITemplateStreamFilter
from trac.web.chrome import add_link
from trac.web.chrome import add_stylesheet
from trac.web.chrome import Chrome
from trac.web.chrome import ITemplateProvider
from tracsqlhelper import get_all_dict, get_column

from StringIO import StringIO

class TracHoursSidebarProvider(Component):


    implements(ITicketSidebarProvider, IRequireComponents)

    ### method for IRequireComponents
    def requires(self):
        return [customerProjects, TicketSidebarProvider]


    ### methods for ITicketSidebarProvider

    def enabled(self, req, ticket):
        if ticket.id and req.authname and 'CUST_EDIT' in req.perm:
            return True
        return False

    def content(self, req, ticket):
        defaultCustomer = int(self.config.get('customerProjects', 'defaultCustomer','0'))

        c_projects = customerProjects(self.env)
        customers = c_projects.getCustomers()
        ticket_p = c_projects.getProjectByTicketId(ticket.id)
        if ticket_p == 'none':
            ticket_p = {'id':0, 'name' : '', 'data': '', 'parentId':0, 'customerId':defaultCustomer, 'active':0, 'workon':0}
        self.log.debug("ticket_p: %r", ticket_p)
        ticket_dictionary = json.dumps(ticket_p)
        add_script(req, 'cp/js/cust.js')
        data = { 'customers' : customers,
                 'action': req.href('c_projects/ticket', ticket.id),
                 'ticket_dictionary' : ticket_dictionary,
                 't_project': ticket_p,
                 'p_base_url' : req.href.c_projects(),
                } 
        return Chrome(self.env).load_template('cust_sidebar.html').generate(**data)


    ### methods for ITemplateProvider

    """Extension point interface for components that provide their own
    ClearSilver templates and accompanying static resources.
    """

    def get_htdocs_dirs(self):
        """Return a list of directories with static resources (such as style
        sheets, images, etc.)

        Each item in the list must be a `(prefix, abspath)` tuple. The
        `prefix` part defines the path in the URL that requests to these
        resources are prefixed with.
        
        The `abspath` is the absolute path to the directory containing the
        resources on the local file system.
        """
        from pkg_resources import resource_filename
        return [('cp', resource_filename(__name__,'htdocs'))]

    def get_templates_dirs(self):
        """Return a list of directories containing the provided template
        files.
        """
        from pkg_resources import resource_filename
        return [resource_filename(__name__, 'templates')]


