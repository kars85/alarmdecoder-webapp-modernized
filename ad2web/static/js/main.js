﻿/* Author: Wilson Xu */

/* Add a flash message notification to the DOM */
function add_flash_message(message, category)
{
    var htmlStr = '<div class="alert alert-' + category + '" data-bs-dismiss="alert"><button type="button" class="close" data-bs-dismiss="alert">x</button>' + message + '</div>';
    $('#flash_message_container').append(htmlStr);
}

/* Determine if text is selected in any input */
function isTextSelected(input)
{
    if( typeof input.selectionStart == "number" )
    {
        return input.selectionStart == 0 && input.selectionEnd == input.value.length;
    }
    else if( typeof document.selection != "undefined")
    {
        input.focus();
        return document.selection.createRange().text == input.value;
    }
}

function hide_flask_message_container() {
    $('#flash_message_container').slideUp('fast');
}

$(document).ready(function() {
    decoder = new AlarmDecoder();
    decoder.init();

    $('.alert').on('click', function(e) {
        $(this).hide();
    });

    $('.alert').on('touchend', function(e) {
        $(this).hide();
    });
// hiding the x overflow on the wrap prevents ios from scrolling, but not having it on android does weird things, so add the style if it's not an ios device
    if( !isiPad && !isiPhone )
    {
        $('#wrap').css('overflow-x', 'hidden');
    }
})
