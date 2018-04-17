$(document).ready(function(e) {
	
	
$('table').on('mousemove', 'td', function(e) {  
	  var tooltipX = event.pageX - 8;
	  var tooltipY = event.pageY + 8;
	  $('div.tooltip').css({top: tooltipY, left: tooltipX});
});

$('table').on('mouseenter', 'td', function(e) {  

    var lcaption = e.delegateTarget.tHead.rows[0].cells[this.cellIndex];
		var lnum  = this.parentNode.cells[0];
		
		$('div.tooltip').remove();
	  $('<div class="tooltip">'+$(lcaption).text()+'</div>').appendTo('body');
	  changeTooltipPosition(event);
});
	
$('table').on('mouseleave', 'td', function(e) {  
	  $('div.tooltip').remove();
});	
	

	
});
