$(document).ready(function(){
    $('.vote').each(function(){
        elem = $(this)
                
        up_button = elem.children('.vote-up')
        down_button = elem.children('.vote-down')

        //HARDCODED VALUES!!!
        up_button.click(function(){
            do_vote($(this), $(this).parent().children('input').val(), 1); 
        });
        down_button.click(function(){
            do_vote($(this), $(this).parent().children('input').val(), 2); 
        });
    });
});

function mod_votecount(button, k){
    count = parseInt(button.siblings('.vote-count').text())
    count += k
    button.siblings('.vote-count').text(count)
}

function toggle_button(button){
    // Toggles the on/off status of a voting button
    if(button.hasClass('vote-on')){
        button.removeClass('vote-on');
        button.addClass('vote-off');
    }else if(button.hasClass('vote-off')){
        button.removeClass('vote-off');
        button.addClass('vote-on');
    }
    // Turn off opposite buttons if they're on
    if(button.hasClass('vote-on')){ 
        if(button.hasClass('vote-up')) 
            toggle_button(button.siblings('.vote-down.vote-on'))
        if(button.hasClass('vote-down'))
            toggle_button(button.siblings('.vote-up.vote-on'))       
    }
    // Update the vote counts immediately
    if(button.is('.vote-up.vote-on, .vote-down.vote-off'))
        mod_votecount(button, +1)
    if(button.is('.vote-up.vote-off, .vote-down.vote-on'))
        mod_votecount(button, -1)
    
}

function popover(parent, msg, cls){
    parent.append('<div></div>')
    elem = parent.children('div')
    elem.addClass('popover ' + cls)
    elem.text(msg)
    elem.delay(1000).fadeOut(1000, function(){
        $(this).remove() 
    });
}

function do_vote(button, post, type){
    toggle_button(button) // Pre-emptitively toggle the button to provide feedback
    $.post('/vote/' , {post:post, type:type},
    function(data){
        popover(button.parent(), data.msg, data.status)
        if(data.status == 'error'){
            toggle_button(button) // Untoggle the button if there was an error
        }
    }, 'json');
}