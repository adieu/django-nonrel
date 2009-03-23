var Actions = {
    init: function() {
        selectAll = document.getElementById('action-toggle');
        if (selectAll) {
            selectAll.style.display = 'inline';
            addEvent(selectAll, 'change', function() {
                Actions.checker(this.checked);
            });
        }
    },
    checker: function(checked) {
        actionCheckboxes = document.getElementsBySelector('tr input.action-select');
        for(var i = 0; i < actionCheckboxes.length; i++) {
            actionCheckboxes[i].checked = checked;
        }
    }
}

addEvent(window, 'load', Actions.init);
