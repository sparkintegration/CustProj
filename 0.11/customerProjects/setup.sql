

create table customers ( id integer primary key autoincrement, name text, data text);
create table c_projects (id integer primary key autoincrement, parentId integer,
            customerId integer,
            name text,
            data text,
            budget integer default 0,
            active boolean default 1,
            workon boolean default 1);

