﻿    <script type="text/javascript">
        //are we paused?
        var bPaused = false;
        //store messages when paused, display later
        var messagesBacklog = [];
        $(document).ready(function() {
            $.fn.dataTableExt.oPagination.iFullNumbersShowPages = 3;
            $.fn.dataTableExt.oApi.fnStandingRedraw = function(oSettings) {
                if( oSettings.oFeatures.bServerSide === false )
                {
                    //what page were we looking at?
                    var before = oSettings._iDisplayStart;
                    oSettings.oApi._fnReDraw(oSettings);
                    //set the display start to what page we were looking at before
                    oSettings._iDisplayStart = before;
                    oSettings.oApi._fnCalculateEnd(oSettings);
                }
                oSettings.oApi._fnDraw(oSettings);
            };
            PubSub.subscribe('message', function(type, msg) {
                var n = new Date();
                var day = ('0' + (n.getDay())).slice(-2);
                var month = ('0' + (n.getMonth() + 1)).slice(-2);
                var year = n.getFullYear();
                var hour = ('0' + (n.getHours())).slice(-2);
                var min = ('0' + (n.getMinutes())).slice(-2);
                var sec = ('0' + (n.getSeconds())).slice(-2);
                var datetime = day + "/" + month + "/" + year + " " + hour + ":" + min + ":" + sec;

                //remove microseconds
                var timestamp = msg.timestamp.slice(0, msg.timestamp.indexOf("."));;

                if( !bPaused )
                {
                    //if we're unpaused and have messages in the backlog, present them
                    if(messagesBacklog.length > 0)
                    {
                        for( i = 0; i < messagesBacklog.length; i++ )
                        {
                            $('#card-log').dataTable().fnAddData([messagesBacklog[i].tstamp, messagesBacklog[i].message], false);
                            $('#card-log').dataTable().fnStandingRedraw();
                        }
                        //empty the backlog array as we've added the contents to the table already
                        messagesBacklog = [];
                        messagesBacklog.length = 0;
                    }
                    $('#card-log').dataTable().fnAddData([ timestamp, msg.raw], false);
                    $('#card-log').dataTable().fnStandingRedraw();
                }
                else
                {
                    //if we're paused, save messages in an array to add when unpaused.
                    messagesBacklog.push({tstamp:timestamp, message:msg.raw});
                }
            });
            $.fn.spin.presets.flower = {
                lines: 13,
                length: 30,
                width: 10,
                radius: 30,
                className: 'spinner',
            }
            $('#loading').spin('flower');
            var oTable = $('#card-log').dataTable({
                "oTableTools": {
                    "aButtons": [ "print",
                                {
                                    "sExtends": "collection",
                                    "sButtonText": "Save",
                                    "aButtons": [ "csv", "xls", "pdf" ]
                                }
                                ],
                    "sSwfPath": "{{ url_for('static', filename='copy_csv_xls_pdf.swf') }}",
                },
                "bStateSave": true,
                "iCookieDuration": 60*60*24,
                "sPaginationType": "full_numbers",
                "aaSorting": [[0, "desc" ]],
                "oLanguage": {
                    "sInfoFiltered": "",
                    "sInfo": "_START_ to _END_ of _TOTAL_",
                    "sInfoEmpty": "No Results",
                    "sInfoThousands": "",
                    "sEmptyTable": " ",
                },
                "fnInitComplete": function() {
                    $('#loading').stop();
                    $('#loading').hide();
                    $('#datatable').show();
                    $('#clear').css('display', 'block');
                    this.fnAdjustColumnSizing();
                },
            });
            var tt = new $.fn.dataTable.TableTools(oTable, { "sSwfPath": "{{ url_for('static', filename='copy_csv_xls_pdf.swf')}}"});
            $(tt.fnContainer() ).insertBefore('div.dataTables_wrapper');
            $('#clearbutton').on('click', function() {
                $.confirm({
                    content: "Are you sure?",
                    title: "Clear Event Log",
                    confirm: function(button) {
                        oTable.fnClearTable();
                    },
                    cancel: function(button) {
                    },
                    confirmButton: "Yes",
                    cancelButton: "No",
                    post: false,
                });
            });
            $('#pausebutton').on('click', function() {
                bPaused = !bPaused;

                if( !bPaused )
                    $('#pausebutton').text("Pause");
                else
                    $('#pausebutton').text("Unpause");
            });
            $(document).keydown(function(event) {
                var shiftKey = event.shiftKey;
                var charCode = (typeof event.which == "number") ? event.which : event.keyCode;
                var realCharCode = String.fromCharCode(charCode);
//F1-F4
                if( charCode == 112 )
                {
                    $.confirm({
                        content: "Are you sure?",
                        title: "Call the Fire Department",
                        confirm: function(button) {
                            add_flash_message("Fire Department notified.", "error");
                            decoder.emit('keypress', 1);
                        },
                        cancel: function(button) {
                        },
                        confirmButton: "Yes I am",
                        cancelButton: "No",
                        post: false,
                    });
                }
                if( charCode == 113 )
                {
                    $.confirm({
                        content: "Are you sure?",
                        title: "Call the Police Department",
                        confirm: function(button) {
                            add_flash_message("Police Department notified.", "error");
                            decoder.emit('keypress', 2);
                        },
                        cancel: function(button) {
                        },
                        confirmButton: "Yes I am",
                        cancelButton: "No",
                        post: false,
                    });
                }
                if( charCode == 114 )
                {
                    $.confirm({
                        content: "Are you sure?",
                        title: "Call the Medics",
                        confirm: function(button) {
                            add_flash_message("Medical Help notified.", "error");
                            decoder.emit('keypress', 3);
                        },
                        cancel: function(button) {
                        },
                        confirmButton: "Yes I am",
                        cancelButton: "No",
                        post: false,
                    });
                }
                if( charCode == 115 )
                {
                    $.confirm({
                        content: "Are you sure?",
                        title: "Confirmation required",
                        confirm: function(button) {
                            add_flash_message("Notification sent.", "error");
                            decoder.emit('keypress', 4);
                        },
                        cancel: function(button) {
                        },
                        confirmButton: "Yes I am",
                        cancelButton: "No",
                        post: false,
                    });
                }

//the rest
                if( charCode == 8 || charCode == 9 || charCode == 46 || charCode == 37 || charCode == 39 || (charCode >= 48 && charCode <= 57) || (charCode >= 96 && charCode <= 105 ))
                {
                    if( shiftKey )
                    {
                        if(charCode == 56)
                        {
                            decoder.emit('keypress', '*');
                        }
                        if(charCode == 51)
                        {
                            decoder.emit('keypress', '#');
                        }
                    }
                    else
                    {
                        decoder.emit('keypress', realCharCode);
                    }
                }
            });

        });
    </script>
