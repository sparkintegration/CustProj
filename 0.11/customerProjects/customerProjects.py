import re
import datetime
import json
import time

from trac.core import *
from trac.util import Markup
from trac.web import IRequestHandler
from trac.timeline import ITimelineEventProvider
from trac.web.chrome import INavigationContributor, ITemplateProvider, add_stylesheet, add_script, Chrome
from trac.web.api import ITemplateStreamFilter
from trac.perm import IPermissionRequestor
from trac.wiki import wiki_to_html
from trac.mimeview.api import Context
from trac.web.chrome import add_warning
from tracsqlhelper import *
# imports get_all_dict and get_column
from genshi.builder import tag
from genshi.filters import Transformer
from genshi.filters.transform import StreamBuffer

class customerProjects(Component):
    implements(IRequestHandler, ITemplateProvider, INavigationContributor, IPermissionRequestor, ITemplateStreamFilter)
      # ITimelineEventProvider

    # INavigationContributor methods
    def get_active_navigation_item(self, req):
        return 'Projects'
        
    def get_navigation_items(self, req):
        if not req.perm.has_permission('CUST_VIEW'):
            return
        yield 'mainnav', 'Projects', \
               tag.a('Projects', href=req.href.c_projects())
    
    ### method for ITemplateStreamFilter
    def filter_stream(self, req, method, filename, stream, data):
        """
        filter project fields to have it 
        correctly display on the ticket.html
        """

        if filename == 'ticket.html':
            project = [ field for field in data['fields'] if field['name'] == 'project' ][0] 
            ticket_id = data['ticket'].id
            if ticket_id is None: # new ticket
                field = 'none'
            else:
                proj = self.getProjectByTicketId(ticket_id)
                if proj == 'none':
                     field = 'none'
                else: 
                     field = tag.a(proj['name'], href=req.href('c_projects', proj['id']), title="Project for ticket %s" % data['ticket'].id)
            project['rendered'] = field
            stream |= Transformer("//input[@id='field-project']").replace(field)

            customer = [ c_field for c_field in data['fields'] if c_field['name'] == 'customer' ][0]
            if ticket_id is None: # new ticket
                c_field = 'none'
            else:
                if proj != 'none':
                    cust = self.getCustomerByProjectId(proj['id'])
                    c_field = tag.a(cust['name'], href=req.href('cust','projects', cust['id']), title="Customer for ticket %s" % data['ticket'].id)
                else: 
                    c_field = 'none'
            customer['rendered'] = c_field

            stream |= Transformer("//input[@id='field-customer']").replace(c_field)

        return stream
 
    #IRequestProvider functions
    def match_request(self, req):
        """
        Matches requests to the /cust URL.  Only matches if the current user has CUST_VIEW permission.
        Puts the rest of the request after /cust/ into a variable called 'rest' in the req.args dictionary
        """
        if not req.perm.has_permission('CUST_VIEW'):
            return False
        c_match = re.match(r'/cust/(.*?)$', req.path_info)
        if c_match or req.path_info == '/cust':
            if c_match:
                req.args['rest'] = c_match.group(1)
            else:
                req.args['rest'] = ""
            req.args['type'] = 'customer'
            return True
        p_match = re.match(r'/c_projects/(.*?)$', req.path_info)
        if p_match or req.path_info == '/c_projects':
            if p_match:
                req.args['rest'] = p_match.group(1)
            else:
                req.args['rest'] = ""
            req.args['type'] = 'project'
            return True
 
    def process_request(self, req):
        if req.args['type'] == 'customer':
            self.handlers = {'':self.customers, 'edit':self.edit_customer, 'add':self.add_customer, 'projects':self.getCustomerProjects, 
                                'tickets':self.getCustomerTickets, 'list':self.listCustomerProjects,}
            cmds = req.args['rest'].split('/')
            #call a handler based on  the first argument
            self.log.debug("Processing: %r", cmds)
            if cmds[0] in self.handlers:
                return self.handlers[cmds[0]](req)
            else:
                return self.customers(req)

        if req.args['type'] == 'project':
            self.handlers = {'':self.projects, 'edit':self.edit_project, 'add':self.add_project, 
                             'update':self.update_projects, 'ticket': self.updateTicket, 'tickets':self.get_tickets}
            cmds = req.args['rest'].split('/')
            #call a handler based on  the first argument
            self.log.debug("Processing: %r", cmds)
            if cmds[0] in self.handlers:
                return self.handlers[cmds[0]](req)
            else:
                p_id_match = re.match(r'(\d*)',cmds[0])
                if p_id_match:
                    return self.subProjects(req,p_id_match.group(1))
            return self.projects(req)

    def listCustomerProjects(self,req):
        cmds = req.args['rest'].split('/')
        #get the customerId from the URL
        id = cmds[1]
        if id:
            projects = self.getParentProjectsByCustomerId(id)
        else:
            projects = {}
        p_dict = []
        for project in projects:
            p_dict.append(['%s' % project['id'],'%s' % project['name'], project['workon'], project['active']])
            subProjects = self.getSubProjectsByProjectId(project['id'])
            for sub in subProjects:
                p_dict.append([sub['id'],sub['name'], sub['workon'], sub['active']])
        project_dictionary = json.dumps(p_dict)
        req.send(project_dictionary)

    def projects(self,req):
        add_stylesheet(req, 'cp/css/customers.css')
        projects = self.getProjects()
        inactive_count = 0
        ticketCountP = self.getTicketCountByProject()
        projectTimes = self.getProjectTime()
        for project in projects:
            if ticketCountP.has_key('%s' % project['id']):
                project['ticketCount'] = ticketCountP['%s' % project['id']]
            else:
                project['ticketCount'] = 0

            if projectTimes.has_key('%s' % project['id']):
                project['totalTime'] = projectTimes['%s' % project['id']]
            else:
                project['totalTime'] = '0:00'
            if project['active'] == 0:
                project['class'] = 'inactive'
                project['style'] = 'display: none'
                inactive_count += 1
        customers = self.getCustomers()
        url = req.abs_href(req.path_info)
        edit = req.perm.has_permission('CUST_EDIT')
        data = locals().copy()
        data['c_base_url'] = req.href.cust()
        data['p_base_url'] = req.href.c_projects()
        data['t_base_url'] = req.href.ticket()
        del data['self']
        del data['projectTimes']
        del data['ticketCountP']
        add_script(req, 'cp/js/cust.js')

        return 'projects.html',data,None
 
    def getCustomerTickets(self,req):
        add_stylesheet(req, 'cp/css/customers.css')
        cmds = req.args['rest'].split('/')
        #get the customerId from the URL
        id = cmds[1]
        self.log.debug(" Getting tickets for customer %s",id)
        tickets = self.getTicketsByCustomerId(id)
        customer = self.getCustomerById(id)
        if customer == None:
            add_warning(req,"Project does not exist %s" % id)
            return self.customers(req)
        url = req.abs_href(req.path_info)

        edit = req.perm.has_permission('CUST_EDIT')
        data = locals().copy()
        del data['self']
        data['c_base_url'] = req.href.cust()
        data['p_base_url'] = req.href.c_projects()
        data['t_base_url'] = req.href.ticket()
        return 'c_tickets.html',data,None

        
    def getCustomerProjects(self,req):
        add_stylesheet(req, 'cp/css/customers.css')
        add_script(req, 'cp/js/cust.js')
        cmds = req.args['rest'].split('/')
        self.log.debug("Customer Projects cmds: %r",cmds)
        c_id_match = re.match(r'(\d+)',cmds[1])
        if c_id_match:
            id = c_id_match.group(1)
        else:
            id = 0
        customer = self.getCustomerById(id)
        if customer == None:
            add_warning(req,"Customer does not exist %s" % id)
            return self.customers(req)
        projects = self.getProjectsByCustomerId(id)
        inactive_count = 0
        ticketCountP = self.getTicketCountByProject() 
        projectTimes = self.getProjectTime()
        for project in projects:
            if ticketCountP.has_key('%s' % project['id']):
                project['ticketCount'] = ticketCountP['%s' % project['id']]
            else:
                project['ticketCount'] = 0

            if projectTimes.has_key('%s' % project['id']):
                project['totalTime'] = projectTimes['%s' % project['id']]
            else:
                project['totalTime'] = 0
            if project['active'] == 0:
                project['class'] = 'inactive'
                project['style'] = 'display: none'
                inactive_count += 1
        url = req.abs_href(req.path_info)
        edit = req.perm.has_permission('CUST_EDIT')
        data = locals().copy()
        self.log.debug("TicketCountP : %r",ticketCountP)
        del data['self']
        del data['ticketCountP']
        del data['projectTimes']
        data['t_base_url'] = req.href.ticket()
        data['c_base_url'] = req.href.cust()
        data['p_base_url'] = req.href.c_projects()
        return 'custProjects.html',data,None
 

    def subProjects(self,req,id):
        add_stylesheet(req, 'cp/css/customers.css')
        add_script(req, 'cp/js/cust.js')
        projects = self.getSubProjects(id, active=1)
        inactive_projects = self.getSubProjects(id, inactive=1)
        inactive_count = len(inactive_projects)
        main_project = self.getProjectByProjectId(id)
        if main_project == 'none':
            add_warning(req,"Project does not exist %s" % id)
            return self.projects(req)
        tickets = self.getTicketsByProjectId(id)
        ticketCountP = self.getTicketCountByProject()
        projectTimes = self.getProjectTime()
        for project in projects:
            if ticketCountP.has_key('%s' % project['id']):
                project['ticketCount'] = ticketCountP['%s' % project['id']]
            else:
                project['ticketCount'] = 0

            if projectTimes.has_key('%s' % project['id']):
                project['totalTime'] = projectTimes['%s' % project['id']]
            else:
                project['totalTime'] = 0

        if ticketCountP.has_key('%s' % main_project['id']):
            main_project['ticketCount'] = ticketCountP['%s' % main_project['id']]
        else:
            main_project['ticketCount'] = 0
        url = req.abs_href(req.path_info)
        edit = req.perm.has_permission('CUST_EDIT')
        data = locals().copy()
        del data['self']
        del data['ticketCountP']
        data['c_base_url'] = req.href.cust()
        data['t_base_url'] = req.href.ticket()
        data['p_base_url'] = req.href.c_projects()
        return 'subProjects.html',data,None

    def get_tickets(self,req):
        add_stylesheet(req, 'cp/css/customers.css')
        cmds = req.args['rest'].split('/')
        #get the projectId from the URL
        id = cmds[1]
        self.log.debug(" Getting tickets for project %s",id)
        tickets = self.getTicketsByProjectId(id)
        main_project = self.getProjectByProjectId(id)
        if main_project == 'none':
            add_warning(req,"Project does not exist %s" % id)
            return self.projects(req)
        url = req.abs_href(req.path_info)
        edit = req.perm.has_permission('CUST_EDIT')
        data = locals().copy()
        del data['self']
        data['c_base_url'] = req.href.cust()
        data['p_base_url'] = req.href.c_projects()
        data['t_base_url'] = req.href.ticket()
        return 'tickets.html',data,None

    def updateTicket(self,req):
        add_stylesheet(req, 'cp/css/customers.css')
        if req.method == "POST" and 'projectId' in req.args:
            cmds = req.args['rest'].split('/')
            ticket_id = cmds[1]
            self.log.debug("updating project for ticket: %s", ticket_id)
            project_id = req.args['projectId']
        else:
            location = req.environ.get('HTTP_REFERER', req.href(req.path_info))
            req.redirect(location)
     
        qry = "update ticket_custom set value=%s where ticket=%s and name='project'"
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry,(project_id, ticket_id))

        location = req.environ.get('HTTP_REFERER', req.href(req.path_info))
        req.redirect(location)
 
    def customers(self,req):
        add_stylesheet(req, 'cp/css/customers.css')
        add_script(req, 'cp/js/cust.js')
        customers = self.getCustomersExtended()
        edit = req.perm.has_permission('CUST_EDIT')
        data = locals().copy()
        del data['self']
        data['t_base_url'] = req.href.ticket()
        data['c_base_url'] = req.href.cust()
        data['p_base_url'] = req.href.c_projects()
        return 'customers.html',data,None

    def add_project(self,req):
        self.log.debug("project Add:  %r", req)
        self.log.debug("project Add Args: %r", req.args)
        return self.do_project_add(req)

    def update_projects(self,req):
        self.log.debug("Project updates: %r",req)
        self.log.debug("project update args: %r", req.args)
        return self.do_project_update(req)

    def add_customer(self,req):
        self.log.debug("Customer Add:  %r", req)
        self.log.debug("Customer Add Args: %r", req.args)
        return self.do_customer_add(req)

    def process_project(self, req):
        """Process request to /c_project/<projectId>"""

        #get the Project
        self.log.debug("Got req: %r", req)
        path = req.path_info.rstrip('/')
        projectId = int(path.split('/')[-1]) #matches projectId

        if req.method == "POST":
           if req.args.has_key('edit'):
              return self.do_project_change(req,projectId)

           if req.args.has_key('add'):
              return self.do_project_add(req,projectId)
        else:
            return self.projects(req)

    def process_customer(self, req):
        """Process request to /cust/<customerId>"""

        #get the Customer
        self.log.debug("Got req: %r", req)
        path = req.path_info.rstrip('/')
        customer = int(path.split('/')[-1]) #matches customerId
       
        if req.method == "POST":
            if req.args.has_key('edit'):
                 return self.do_customer_change(req,customer)
    
            if req.args.has_key('add'):
                 return self.do_customer_add(req,customer)
        else:
             return self.customers(req)

    def do_customer_change(self,req,customer):
        self.log.debug("Got change Request: %r", req)
        return self.customers(req)


    def do_customer_add(self,req):
        self.log.debug("Got add Request: %r", req)
        if req.method == "POST":
            customer_name = req.args['c_name']       
            customer_data = req.args['c_description']
            if customer_name == '' or customer_data == '':
                self.log.debug("Not adding blank customer info")
                add_warning(req, "Name or Description cannot be blank")
                return self.customers(req)
            
            customers = self.getCustomers()
            dupe=0
            for customer in customers:
                if customer['name'].upper() == customer_name.upper():
                   dupe=1
            if dupe==1:
                add_warning(req,"Duplicate customer Name: %s" % customer_name) 
            else:
                newCustId = self.addCustomer(customer_name, customer_data)
                self.log.debug("Added customer with ID: %s", newCustId)
        return self.customers(req)

    def do_project_update(self,req):
        if req.method == "POST":
            activeList = []
            workList = []
            for key, value in req.args.items():
              active_match = re.match(r'active_(.*?)$', key)
              work_match = re.match(r'workon_(.*?)$', key)
              if active_match:
                activeList.append(active_match.group(1))
              if work_match:
                workList.append(work_match.group(1))

            if req.args.has_key('ids'):
                if isinstance(req.args['ids'],list):    
                    allList = req.args['ids']
                else:
                    allList = [req.args['ids'],]
            else:
                location = req.environ.get('HTTP_REFERER', req.href(req.path_info))
                req.redirect(location)
            
            inactiveList = [item for item in allList if item not in activeList] 
            vars_active = ','.join(activeList)
            vars_inactive = ','.join(inactiveList)
 
            qry_on = """update c_projects set active=1 where id in (%s)""" % vars_active
            qry = """update c_projects set active=0 where id in (%s)""" % vars_inactive
            db = self.env.get_db_cnx()
            cursor = db.cursor()
            if len(activeList) > 0:
                cursor.execute(qry_on)
            if len(inactiveList) > 0:
                cursor.execute(qry)
            
            noWorkList = [item for item in allList if item not in workList] 
            vars_work = ','.join(workList)
            vars_noWork = ','.join(noWorkList)

            qry_on = """update c_projects set workon=1 where id in (%s)""" % vars_work
            qry = """update c_projects set workon=0 where id in (%s)""" % vars_noWork
            db = self.env.get_db_cnx()
            cursor = db.cursor()
            if len(workList) > 0:
                cursor.execute(qry_on)
            if len(noWorkList) > 0:
                cursor.execute(qry)

            self.log.debug("Active: %r", activeList)
            self.log.debug("Work: %r", workList)
            self.log.debug("All: %r", allList)

        location = req.environ.get('HTTP_REFERER', req.href(req.path_info))
        req.redirect(location)

 #return self.projects(req)

    def do_project_add(self,req):
        self.log.debug("Got project add Request: %r", req)
        location = req.environ.get('HTTP_REFERER', req.href(req.path_info))
        if req.method == "POST":
            project_name = req.args['p_name']
            project_data = req.args['p_description']
            if 'p_customerId' in req.args:
                project_custId = req.args['p_customerId']
            else:
                add_warning(req,"Must have at least 1 customer before adding projects")
                req.redirect(location)
            project_parentId = req.args.get('p_projectId', 0)
            self.log.debug("parent: %r", project_parentId)
            if project_parentId == '':
                project_parentId = 0
            if project_name == '' or project_data == '':
                self.log.debug("Not adding blank project info")
                add_warning(req, "Name or Description cannot be blank")
                req.redirect(location)
            project_budget = req.args['p_budget']
            dupe=0
            projects = self.getProjects()
            for project in projects:
                if project['name'].upper() == project_name.upper():
                   dupe=1
            if dupe==1:
                add_warning(req,"Duplicate project name: %s" % project_name)
            else:
                newProjectId = self.addProject(project_name, project_data, project_custId, project_parentId, project_budget)
                #    def addProject(self, name, data, customerId, parentId):
                self.log.debug("Added Project with ID: %r", newProjectId)
        req.redirect(location)

    def edit_project(self,req):
        if req.method == "POST":
            project_name = req.args['p_name']
            project_data = req.args['p_description']
            if 'p_active' in req.args:
                project_active = 1
            else:
                project_active = 0
            project_id = req.args['p_id']
            if 'p_customerId' in req.args:
                project_custId = req.args['p_customerId']
            else:
                add_warning(req,"Must have at least 1 customer before adding projects")
                return self.edit_p_helper(req)
            project_parentId = req.args['p_projectId']
            if project_parentId == '':
                project_parentId = 0
            if project_name == '' or project_data == '':
                self.log.debug("Not adding blank project info")
                add_warning(req, "Name or Description cannot be blank")
                return self.edit_p_helper(req)
            project_budget = req.args['p_budget']
            if 'p_workon' in req.args:
                project_workon = 1
            else:
                project_workon = 0
            dupe=0
            projects = self.getProjects()
            for project in projects:
                if (project['name'].upper() == project_name.upper()) and (int(project_id) != int(project['id'])):
                   self.log.debug("project_id = %s ",project_id)
                   self.log.debug("project[id] = %s", project['id'])
                   dupe=1
            if dupe==1:
                add_warning(req,"Duplicate project name: %s" % project_name)
                return self.edit_p_helper(req)
            else:
                self.updateProject(project_id, project_name, project_data, project_custId, project_parentId,project_active,project_workon,project_budget)
                self.log.debug("Edited Project with info: %r", req.args)

        else:
            return self.edit_p_helper(req)
        
        location = req.environ.get('HTTP_REFERER', req.href(req.path_info))
        if 'orig_url' in req.args:
            orig_url = req.args['orig_url']
            self.log.debug("Got orig_url: %s", orig_url)
        else:
            orig_url = location
        
        req.redirect(orig_url)
#         return self.projects(req)

    def edit_p_helper(self, req):
        add_stylesheet(req, 'cp/css/customers.css')
        self.log.debug("Got project edit Request: %r", req)
        location = req.environ.get('HTTP_REFERER', req.href(req.path_info))
        if 'orig_url' in req.args:
            orig_url = req.args['orig_url']
        else:
            orig_url = location

        cmds = req.args['rest'].split('/')
        project_id = cmds[1]
        project = self.getProjectByProjectId(project_id)
        cust_id = project['customerId']

        parents = self.getParentProjectsByCustomerId(cust_id)
        projects = []
        for proj_ in parents:
            projects.append(proj_)
            subProjects = self.getSubProjectsByProjectId(proj_['id'])
            for sub in subProjects:
                projects.append(sub)
        # self.log.debug("Projects: %r", projects)
        # projects = self.getProjectsByCustomerId(cust_id)
        url = req.abs_href(req.path_info)
        edit = req.perm.has_permission('CUST_EDIT')
        data = locals().copy()
        del data['self']
        data['t_base_url'] = req.href.ticket()
        data['c_base_url'] = req.href.cust()
        data['p_base_url'] = req.href.c_projects()
        return 'p_edit.html',data,None

    def edit_customer(self,req):
        self.log.debug("Got Customer edit Request: %r", req)
        location = req.environ.get('HTTP_REFERER', req.href(req.path_info))
        if 'orig_url' in req.args:
            orig_url = req.args['orig_url']
        else:
            orig_url = location

        if req.method == "POST":
            customer_name = req.args['c_name']
            customer_data = req.args['c_description']
            customer_id = req.args['c_id']
            if customer_name == '' or customer_data == '':
                add_warning(req, "Name or Description cannot be blank")
                req.redirect(location)
            dupe=0
            customers = self.getCustomers()
            for cust in customers:
                if (cust['name'].upper() == customer_name.upper()) and (int(customer_id) != int(cust['id'])):
                   dupe=1
            if dupe==1:
                add_warning(req,"Duplicate Customer name: %s" % customer_name)
            else:
                self.updateCustomer(customer_id, customer_name, customer_data)
        else:
            cmds = req.args['rest'].split('/')
            if (len(cmds) > 1) and cmds[1]: 
                cust_id = cmds[1]
                customer = self.getCustomerById(cust_id)
                url = req.abs_href(req.path_info)
                edit = req.perm.has_permission('CUST_EDIT')
                data = locals().copy()
                del data['self']
                data['c_base_url'] = req.href.cust()
                data['t_base_url'] = req.href.ticket()
                data['p_base_url'] = req.href.c_projects()
                return 'c_edit.html',data,None
            else:
                return self.customers(req)
        return self.customers(req)
        # req.redirect(orig_url)


    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename(__name__, 'templates')]

    def get_htdocs_dirs(self):
        from pkg_resources import resource_filename
        return [('cp', resource_filename(__name__,'htdocs'))]

    def get_permission_actions(self):
        """
        Returns Permissions use by this plugin
        """

        return ['CUST_EDIT','CUST_REPORT','CUST_VIEW']

    def getProjects(self,active=0,inactive=0,workon=0):
        """
        Returns an array of dictionaries containing project names and data, keyed by project id
        """
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        qry = "SELECT a.id, a.name, a.data, a.parentId, coalesce((select name from c_projects where a.parentId=id),'none'),a.customerId, a.active, b.name,a.workon,a.budget  FROM c_projects as a left join customers as b on a.customerId = b.id"
        order = " order by a.customerId, a.parentId, a.name"
        where = ""
        if workon:
            if active:
                where += " where a.active=1 and a.workon=1 " 
            if inactive:
                where += " where a.active=0 and a.workon=1 "
        else:
            if active:
                where += " where a.active=1 " 
            if inactive:
                where += " where a.active=0 "
    
        qry = qry+where+order
        self.log.debug("Project QRY: %s", qry)
        cursor.execute(qry)
        rows = cursor.fetchall()
        projects = []
        for row in rows:
            t_project = {'id':row[0], 'name' : row[1], 'data': row[2], 
                         'parentId':row[3], 'parentName':row[4], 'customerId':row[5], 'active':row[6], 'customerName':row[7],'workon':row[8],'budget':row[9]}
            projects.append(t_project)
        return projects

    def getSubProjects(self,projectId, active=0, inactive=0):
        """
        Returns a dictionary containing project names and data, keyed by project id
        """
        qry = "SELECT a.id, a.name, a.data, a.parentId, coalesce((select name from c_projects where a.parentId=id),'none'),a.customerId, a.active, b.name,a.workon,a.budget "
        qry += " FROM c_projects as a left join customers as b on a.customerId = b.id"
        where = " where a.parentId=%s " % projectId
        if active:
            where += " and  a.active=1 "
        if inactive:
            where += " and a.active=0 "
        order = " order by a.name"
        qry = qry+where+order
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry)
        rows = cursor.fetchall()
        projects = []
        for row in rows:
            t_project = {'id':row[0], 'name' : row[1], 'data': row[2], 
                         'parentId':row[3], 'parentName':row[4], 'customerId':row[5], 'active':row[6], 'customerName':row[7], 'workon':row[8], 'budget':row[9]}
            projects.append(t_project)
        return projects

    def getProjectsByCustomerId(self, customerId, active=0, inactive=0, workon=0):
        """
        Returns a dictionary containing Projects for particular customer
        """
        qry = "SELECT a.id, a.name, a.data, a.parentId, coalesce((select name from c_projects where a.parentId=id),'none'),a.customerId, a.active, b.name, a.workon,a.budget "
        qry += "FROM c_projects as a left join customers as b on a.customerId = b.id "
        where = " where a.customerId=%s " % customerId
        if active:
            where += " and a.active=1 "
        if inactive:
            where += " and a.active=0 "
        if workon:
            where += " and a.workon=1"
        order = " order by a.parentId, a.name " 
        qry = qry+where+order
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry)
        rows = cursor.fetchall()
        projects = []
        if rows == []:
            return projects
        for row in rows:
            t_project = {'id':row[0], 'name' : row[1], 'data': row[2], 
                         'parentId':row[3], 'parentName':row[4], 'customerId':row[5], 'active':row[6], 'customerName':row[7], 'workon':row[8], 'budget':row[9]}
            projects.append(t_project)
        return projects
    
    def getSubProjectsByProjectId(self, projectId, active=0, inactive=0, workon=0, spacer='>'):
        """
        Returns a dictionary containing Parent Projects for particular customer
        """
        spacer = '--' + spacer
        qry = "SELECT id, name, data, active, workon,budget FROM c_projects "
        where = " where parentId=%s " % projectId
        if active:
            where += " and active=1 "
        if inactive:
            where += " and active=0 "
        if workon:
            where += " and workon=1"
        order = " order by name " 
        qry = qry+where+order
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry)
        rows = cursor.fetchall()
        projects = []
        if rows == []:
            return projects
        for row in rows:
            t_project = {'id':row[0], 'name' : spacer+row[1], 'data': row[2], 'active':row[3], 'workon':row[4], 'budget':row[5]}
            projects.append(t_project)
            subs = self.getSubProjectsByProjectId(row[0],active, inactive, workon, '+' + spacer)
            projects.extend(subs)
        return projects

    def getParentProjectsByCustomerId(self, customerId, active=0, inactive=0, workon=0):
        """
        Returns a dictionary containing Parent Projects for particular customer
        """
        qry = "SELECT id, name, data, active, workon, budget FROM c_projects "
        where = " where customerId=%s " % customerId
        where += " and parentId=0 " 
        if active:
            where += " and active=1 "
        if inactive:
            where += " and active=0 "
        if workon:
            where += " and workon=1"
        order = " order by name " 
        qry = qry+where+order
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry)
        rows = cursor.fetchall()
        projects = []
        if rows == []:
            return projects
        for row in rows:
            t_project = {'id':row[0], 'name' : row[1], 'data': row[2], 'active':row[3], 'workon':row[4], 'budget':row[5]}
            projects.append(t_project)
        return projects

    def getProjectByTicketId(self,ticket_id):
        """
        Returns a project dictionary by looking at the ticket_custom table, getting the projectId from that and then looking up the project.
        """
        t_qry = "select value from ticket_custom where ticket=%s and name='project'" % ticket_id
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(t_qry)
        row = cursor.fetchone()
        if row == None or row[0] == 'none':
            return 'none'
        p_id = row[0]
        p_qry = "select id,name,data,parentId,customerId,active,workon from c_projects where id=%s" % p_id
        cursor.execute(p_qry)
        row = cursor.fetchone()
        if row == None or row[0] == 'none':
            return 'none'
        project = {'id':row[0], 'name' : row[1], 'data': row[2], 'parentId':row[3], 'customerId':row[4], 'active':row[5], 'workon':row[6]}
        return project

    def getProjectByProjectId(self,p_id):
        """
        Returns a project dictionary by looking at the ticket_custom table, getting the projectId from that and then looking up the project.
        """
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        p_qry = "SELECT a.id, a.name, a.data, a.parentId, coalesce((select name from c_projects where a.parentId=id),'none'),a.customerId, a.active, b.name, a.workon, a.budget FROM c_projects as a left join customers as b on a.customerId = b.id where a.id=%s" % p_id
        cursor.execute(p_qry)
        row = cursor.fetchone()
        if row == None:
           return 'none'
        project = {'id':row[0], 'name' : row[1], 'data': row[2], 'parentId':row[3], 'parentName':row[4], 'customerId':row[5], 'active':row[6], 'customerName':row[7],'workon':row[8], 'budget':row[9]}
        return project

        
    def getCustomersExtended(self):
        """
        Returns a dictionary containing Customer names and data
        """
        qry = "select c.id, c.name, c.data, count(customerId) from customers as c left join c_projects as cp on c.id=cp.customerId group by c.id order by c.name"
        # "SELECT id, name, data from customers"
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry)
        rows = cursor.fetchall()
        customers = []
        for row in rows:
            cust = {'id': row[0],  'name' : row[1], 'data' : row[2], 'projectCount':row[3]}
            customers.append(cust)
        return customers

    def getCustomers(self):
        """
        Returns a dictionary containing Customer names and data
        """
        qry = "SELECT id, name, data from customers order by name"
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry)
        rows = cursor.fetchall()
        customers = []
        for row in rows:
            cust = {'id': row[0],  'name' : row[1], 'data' : row[2]}
            customers.append(cust)
        return customers

    def getCustomerById(self,id):
        """
        Returns a dictionary containing Customer names and data
        """
        qry = """SELECT id, name, data from customers where id=%s""" 
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry,(id,))
        row = cursor.fetchone()
        if row == None:
            return None
        else: 
            cust = {'id': row[0],  'name' : row[1], 'data' : row[2]}
            return cust

    def getCustomerByProjectId(self,id):
        """
        Returns customer by project id
        """
        qry = "SELECT customerId from c_projects where id=%s"
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry,(id,))
        row = cursor.fetchone()
        self.log.debug( " Cust Row: %r", row)
        if row == None:
            return None
        custId = row[0]
        c_qry = "SELECT id, name, data from customers where id = %s"
        cursor.execute(c_qry,(custId,))
        row = cursor.fetchone()
        self.log.debug( "2nd Cust Row: %r", row)
        if row == None:
            return None
        cust = {'id':row[0], 'name':row[1],'data':row[2]}
        return cust

    def addCustomer(self, name, data):
        """
        Adds customer data to customers table and returns ID
        """
        qry = """Insert into customers (name, data) values (%s, %s)"""  #  (name, data)
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry,(name,data))
        newCustId = cursor.lastrowid
        db.commit()
        return newCustId
     
 
    def addProject(self, name, data, customerId, parentId, budget):
        """
        Adds Project data to project table and returns ID 
        """
        qry = "Insert into c_projects (`parentId`, `customerId`, `name`, `data`,`active`,`budget`) values (%s, %s, %s,%s,1,%s)" 
        vars = (parentId, customerId, name, data, budget)
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry,vars)
        newProjectId = cursor.lastrowid
        db.commit()
        return newProjectId

    def updateProject(self, project_id, project_name, project_data, project_custId, project_parentId, project_active, project_workon, project_budget):
        """
        updates project with new information from form
        """
 
        qry = "update c_projects set active=%s, name=%s, data=%s, customerId=%s, parentId=%s, workon=%s, budget=%s where id=%s"
        vars = (project_active, project_name, project_data, project_custId, project_parentId, project_workon, project_budget, project_id)
        db = self.env.get_db_cnx()
        cursor=db.cursor()
        cursor.execute(qry,vars)
        db.commit()

    def updateCustomer(self, customer_id, customer_name, customer_data):
        """
        updates customer with information from Form
        """
        qry = "update customers set name=%s,data=%s where id=%s"
        vars = (customer_name, customer_data, customer_id)
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry,vars)
        db.commit()

    def getTicketsByCustomerId(self, customerId):
        """
        Returns tickets associated to customer by customerId
        """
        db = self.env.get_db_cnx()
        cursor = db.cursor()

        qry = """select id from c_projects where customerId=%s"""
        cursor.execute(qry,(customerId,))
        rows = cursor.fetchall()        
        tickets = []
        if rows == []:
            return tickets
        p_ids = ','.join([str(row[0]) for row in rows])
        qry_t = "select t.id, t.type, t.summary, tc.value, (select name from c_projects as cp where cp.id = tc.value) from ticket as t left join ticket_custom as tc on t.id = tc.ticket where tc.name ='project' and tc.value in (%s)" % p_ids
        qry_time = "select t.id, tc.value from ticket as t left join ticket_custom as tc on t.id = tc.ticket where tc.name = 'totalhours'"
        cursor.execute(qry_time)
        time_rows = cursor.fetchall()
        times = {}
        if time_rows != []:
            for time_row in time_rows:
                times['%s' % time_row[0]] = time_row[1]
        cursor.execute(qry_t)
        rows = cursor.fetchall()
        if rows == []:
            return tickets
        for row in rows:
            ticket = {'id':row[0], 'type':row[1],'summary':row[2], 'projectId':row[3], 'projectName': row[4], 'ticketTime':times['%s'%row[0]]}
            tickets.append(ticket)
        return tickets

    def getTicketsByProjectId(self, projectId):
        """ 
        Returns list of tickets associated with a project
        """
        qry = "select t.id, t.type,t.summary from ticket as t left join ticket_custom as tc on t.id = tc.ticket where tc.name ='project' and tc.value=%s" % projectId
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry)
        tickets = []
        rows = cursor.fetchall()
        if rows == None:
            return tickets
        for row in rows:
            t_qry = "select value from ticket_custom where name='totalhours' and ticket=%s " % row[0]
            cursor.execute(t_qry)
            totaltime = cursor.fetchone()
            t_time = '%02d:%02d' % (float(totaltime[0]),int((float(totaltime[0])%1)*60))
            ticket = {'id':row[0], 'type':row[1],'summary':row[2], 'totaltime':t_time}
            tickets.append(ticket)
        return tickets

    def getTicketCountByProjectId(self, projectId):
        """
        returns count of tickets for a project
        """
        qry = "select count(tc.ticket) from ticket_custom as tc where tc.name = 'project' and tc.value=%s" % projectId
        db = sef.env.get_db_cnx()
        cusror = db.cursor()
        cursor.execute(qry)
        count = cursor.fetchone()
        if count == []:
            return 0
        return count[0]

    def getTicketCountByProject(self):
        """
        returns count of tickets for all projects
        """
        ticketCounts = {}
        qry = "select tc.value, count(tc.ticket) from ticket_custom as tc where tc.name = 'project' group by tc.value" 
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry)
        counts = cursor.fetchall()
        if counts == []:
            return ticketCounts
        for count in counts:
            ticketCounts['%s' % count[0]] = count[1]
        return ticketCounts
    
    def getProjectTime(self):
        """
        Returns project time
        """
        projectTimes={}
        qry = "select a.value as projectId, sum(b.value) as projectHours from ticket_custom as a left join ticket_custom as b on a.ticket=b.ticket where a.name='project' and b.name='totalhours' group by a.value"        
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(qry)
        rows = cursor.fetchall()
        if rows == []:
            return projectTimes
        for row in rows:
            ptime = '%02d:%02d' % (float(row[1]),int((float(row[1])%1)*60)) 
            projectTimes['%s' % row[0]] = ptime
        return projectTimes


 




