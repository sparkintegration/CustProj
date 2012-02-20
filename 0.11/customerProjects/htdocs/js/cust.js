

function updateProjects(){
        custId = $("#p_customerId").val();

        var no_dis = $("#p_customerId").attr('no_dis');

        t_pid = 0;
        // active = 0;
        // workon = 0;
        command = 'list';
        
        pid = 0, name=1, workon=2, active=3;

        if (typeof(ticket_d) != "undefined") {
            t_pid = ticket_d['id'];
            //active = ticket_d['active'];
            //workon = ticket_d['workon'];
            }
        if (custId) 
        {
            $.getJSON('/trac/cust/'+ command+'/'+custId, function(data) {
                $("#p_projectId").html("<option value='0'>none</option>");
                $.each(data, function(id, value) {
                    dis = '', dis_t = '';
                    inactive = '';
                    if (value[workon]==0)
                       {   
                        dis_t = ' * ';
                        if (no_dis != 1)
                         { dis = 'disabled=1'; }
                       }
                    if (value[active] == 0)
                        inactive = " (inactive) ";
                    if  (t_pid == value[pid])
                        { $("<option value='"+ value[pid] +"' selected=''>" + value[name] + dis_t + inactive + "</option>").appendTo("#p_projectId"); }
                    else
                        { if (value[active] == 1)
                            { $("<option value='"+ value[pid] +"'" + dis + ">"+ value[name] +"</option>").appendTo("#p_projectId");}
                        }
                    });
                });
         }
}

$(document).ready(function(){
    
    updateProjects();

    $("a.inactive").click(function(e) {
        e.preventDefault();
        $("tr.inactive").toggle();
    });
   
    $("tr:even").addClass("even");


    $("#p_customerId").change(updateProjects);

});

