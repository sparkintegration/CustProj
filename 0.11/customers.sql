DROP TABLE IF EXISTS `customers`;
CREATE TABLE customers ( id integer primary key autoincrement, name text, data text);

DROP TABLE IF EXISTS  `c_projects`;
CREATE TABLE c_projects (id integer primary key autoincrement, parentId integer,
            customerId integer,
            name text,
            data text,
            budget integer default 0,
            active boolean default 1,
            workon boolean default 1);




