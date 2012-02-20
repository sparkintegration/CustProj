from setuptools import find_packages, setup

setup(
    name='customerProjects', version='1.0',
    packages=find_packages(exclude=['*.tests*']),
    include_package_data=True,
    install_requires=['python-dateutil', 
                       'TicketSidebarProvider',
                       'TracSQLHelper'],

    entry_points = """
    [trac.plugins]
    customerProjects.customerProjects = customerProjects.customerProjects
    customerProjects.cpSideBar = customerProjects.cpSideBar
    customerProjects.setup = customerProjects.setup
    """,
    package_data={'customerProjects': ['templates/*.html', 'htdocs/css/*.css', 'htdocs/js/*.js']},
)
