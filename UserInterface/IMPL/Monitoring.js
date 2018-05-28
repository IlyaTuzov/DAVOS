
		var fullsource = #FULLSTAT;
        var minsource =  #MINSTAT;
		var Theaders = #THEADERS;
		var TLogDest = #LOGDESC;        
        var GlobalStatHeaders = #GLOBALHEADERS;
        
        var glob_tblbody;
		var proc_tblbody;
		var labels = [];        
        var update_iteration = 0;
        
		window.addEventListener("load", function() {
            glob_tblbody = CreateTable(GlobalStatHeaders, "GlobalStatistics", document.getElementById("ProgressDiv"));
			proc_tblbody = CreateTable(Theaders, "StatItems", document.getElementById("ProgressDiv"));
            //cells in this table are all clickable - logs for each configuration
            $(proc_tblbody).on('click', 'td', function(e){            
                window.open(TLogDest[this.cellIndex].replace('@', labels[this.parentElement.rowIndex]), '_blank');
            }); 
			setInterval(updateTables, 2000);

            
		});

		function CreateTable(Headers, Id, Container){
			var ctable = document.createElement('table');
			tblbody = document.createElement("tbody");
			tblbody.setAttribute("id", Id);
			ctable.appendChild(tblbody);
			tblheader = ctable.createTHead();
            var headrow = tblheader.insertRow(0);
			for (i=0; i<Headers.length; i++){
				var newCell = document.createElement('th');
                headrow.append(newCell);
				newCell.innerHTML = Headers[i];
			};
			Container.appendChild(ctable);
            Container.appendChild(document.createElement('hr'));
            return(tblbody);
		}
		
		
		function updateTables() {
            var connectstat = document.getElementById("ConnectionStatus");
            if(document.getElementById("ConnectSwitch").checked == true){ 
                var xmlhttp = new XMLHttpRequest();
                //once per 10 requests synchronize full data
                if(update_iteration % 10 == 0){
                    xmlhttp.open("get", fullsource+"?cache="+(Math.random()*1000000), true);                    
                }
                else{
                    xmlhttp.open("get", minsource+"?cache="+(Math.random()*1000000), true);                                        
                };
                xmlhttp.onreadystatechange = function() {
                    if (this.readyState == 4 && this.status == 200) {
                        showResult(this);
                        var d = new Date();
                        connectstat.innerHTML = 'Connected, Last Update (' + d.getHours().pad(2) + ':'+d.getMinutes().pad(2) + ':' + d.getSeconds().pad(2) + '): '  + this.response.length / 1000 + ' Kb';
                        update_iteration++;
                    }
                    else if(this.status == 304){
                        connectstat.innerHTML = 'Please, disable browser caching';                
                    }
                    else{
                        connectstat.innerHTML = 'Connection error';
                    }
                };
                xmlhttp.send(null);
            }
            else{
                connectstat.innerHTML = 'Disconnected';
                
            }
		}

		function showResult(xmlhttp) {
				var xmlDoc = xmlhttp.responseXML.documentElement;				
				addRowsFromXml(xmlDoc.getElementsByTagName("Global"), glob_tblbody, GlobalStatHeaders);
				addRowsFromXml(xmlDoc.getElementsByTagName("Config"), proc_tblbody, Theaders);
			}
			
		function addRowsFromXml(xmlNodes, tableNode, Headers) {
				var newRow, i, j;
				for (i=0; i<xmlNodes.length; i++) {
					if( xmlNodes[i].hasAttribute(Headers[0]) ){
						var key = xmlNodes[i].getAttribute(Headers[0]).split('$')[0];
						var crow = $(tableNode).find('tr:has(td:contains("' + key + '"))');
						if(crow.length > 0) {	//if row for this configuration exists
							srow = crow[0];
							for(j=0;j<Headers.length;j++){
								srow.cells[j].innerHTML = MarkupCell(getXmlAtr(xmlNodes[i], Headers[j]));
							};						
						}
						else {	//create new row
							newRow = tableNode.insertRow(-1);
                            labels[newRow.rowIndex] = xmlNodes[i].getAttribute(Headers[0]).split('$')[0];
							for(j=0;j<Headers.length;j++){
								appendCell(xmlNodes[i], Headers[j], newRow);
							};						
						};
					};				
				}
			}
            
        function MarkupCell(content){
            //plain link format: @[Text@Link]@
            //download link format: @[Text@?Link]@            
            var linklist = content.match(/@\[(.*?@.*?)\]@/g)
            if(linklist != null){
                for(i=0;i<linklist.length;i++){
                    var a = linklist[i].replace("@[","").replace("]@","").split("@");
                    content = content.replace(linklist[i], "<a href=\""+ (a[1].charAt(0) == "?" ? a[1].slice(1) + "\" download>" : a[1] + "\">") +a[0]+"</a>");
                };                            
            };
            var dt = content.split('$');
            var cl = '';
            if(dt.length > 1){
                cl = dt[1];
            };
            return('<div class = "' + cl +'"><pre>' + dt[0] +'</pre></div>');
        }

		function getXmlAtr(XmlNode, atrname){
			if(XmlNode.hasAttribute(atrname)){
				return(XmlNode.getAttribute(atrname));
			}
			else {
				return("-");
			};
		}
		
		function appendCell(XmlNode, atrname, Row){
			var newCell;
			newCell = Row.insertCell(Row.cells.length);
			newCell.innerHTML = MarkupCell(getXmlAtr(XmlNode, atrname));
		}
	
    
    
    //Misc
Number.prototype.pad = function(size) {
      var s = String(this);
      while (s.length < (size || 2)) {s = "0" + s;}
      return s;
    }    