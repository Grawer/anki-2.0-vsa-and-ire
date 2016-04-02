# import wrap utility to bootstrap size up, size down logic
from anki.hooks import wrap, addHook, runHook
# import the webview that controls the browser display of html
from aqt.webview import AnkiWebView
# import the main window object (mw) from ankiqt
from aqt import mw, editcurrent, addcards
# import the "show info" tool from utils.py
from aqt.utils import showInfo, showText, tooltip, showWarning, isMac
from anki.sound import clearAudioQueue
# import all of the Qt GUI library
from anki.db import DB;
from anki import notes, models
from aqt.reviewer import Reviewer

import re;
import unicodedata
import os;
from stat import *
import pickle;
import copy as cp
import string;
from aqt.qt import *
import tempfile
import time
# import all of the Qt GUI library
from PyQt4.QtCore import *
from PyQt4 import QtCore
from PyQt4.QtGui import *
from PyQt4.QtWebKit import QWebPage, QWebView, QWebSettings
from PyQt4.QtNetwork import QLocalServer, QLocalSocket
#from PyQt4 import pyqtconfig
from aqt.main import AnkiQt;

class ViewManager():
    def __init__(self, main):
        self.mw = main;
        # Variable to hold the current size multiplier
        self.textSizeMultiplier = 1;
        # Variable to hold scroll position
        self.verticalScrollPosition = 0;
        # Variable to hold quick keys
        self.quickKeys = {};
        self.lastDialogQuickKey = {};
        # Variable to hold the createShortcutMenuItem
        self.createShortcutMenuItem = None;
        self.sizeUpAction = None;
        self.sizeDownAction = None;
        # Track number of times add cards shortcut dialog is opened
        self.acsCount = 0;
        # Track number of times vsa_resetRequiredState function is called (should be same or 1 behind acsCount)
        self.rrsCount = 0;
        # Track number of times vsa_reviewState function is called (should be same or 1 behind acsCount)
        self.rsCount = 0;

        
    # Increase text size
    def sizeUp(self):
        zoomFactor = self.textSizeMultiplier * 1.2;
        self.setZoomFactor(zoomFactor);
        
    # Decrease text size
    def sizeDown(self):
        zoomFactor = self.textSizeMultiplier * .83;
        self.setZoomFactor(zoomFactor);
            
    def setZoomFactor(self, zoomFactor):
        self.textSizeMultiplier = zoomFactor;
        mw = self.mw;
        mw.web.setTextSizeMultiplier(self.textSizeMultiplier);
        self.savePluginData(); #ToDo - decide if we really need to do this every zoom adjustment

    # For future use:  To implement save point so page automatically scrolls to the right location when returning to a lengthy note (incremental reading)
    def saveScrollPosition(self):
        mw = self.mw;
        self.verticalScrollPosition = mw.web.page().mainFrame().scrollPosition().y();
        
    # For future use:  To implement save point so page automatically scrolls to the right location when returning to a lengthy note (incremental reading)
    def restoreScrollPosition(self):
        mw = self.mw;
        mw.web.page().mainFrame().setScrollPosition(QPoint(0, self.verticalScrollPosition));
    
    def getScrollPosition(self):
        return mw.web.page().mainFrame().scrollPosition().y();
    
    def setScrollPosition(self, position):
        self.verticalScrollPosition = position;
        self.restoreScrollPosition();
       
    # Implement page up function
    def pageUpAction(self):
        mw = self.mw;
        self.verticalScrollPosition = mw.web.page().mainFrame().scrollPosition().y();
        size = mw.web.page().viewportSize().height();
        size = (size - (size/20));
        self.verticalScrollPosition = max(0,(self.verticalScrollPosition - size));
        mw.web.page().mainFrame().setScrollPosition(QPoint(0, self.verticalScrollPosition));
     
    #Implement page down function    
    def pageDownAction(self):
        mw = self.mw;
        self.verticalScrollPosition = mw.web.page().mainFrame().scrollPosition().y();
        maxHeight = mw.web.page().mainFrame().scrollBarMaximum(Qt.Vertical);
        size = mw.web.page().viewportSize().height();
        size = (size - (size/20));
        self.verticalScrollPosition = min(maxHeight, (self.verticalScrollPosition + size));
        mw.web.page().mainFrame().setScrollPosition(QPoint(0, self.verticalScrollPosition));

    #Implement arrow or line up action
    def lineUpAction(self):
        mw = self.mw;
        self.verticalScrollPosition = mw.web.page().mainFrame().scrollPosition().y();
        size = (mw.web.page().viewportSize().height()/20);
        self.verticalScrollPosition = max(0,(self.verticalScrollPosition - size));
        mw.web.page().mainFrame().setScrollPosition(QPoint(0, self.verticalScrollPosition));
       
    #Implement arrow or line down action  
    def lineDownAction(self):
        mw = self.mw;
        self.verticalScrollPosition = mw.web.page().mainFrame().scrollPosition().y();
        maxHeight = mw.web.page().mainFrame().scrollBarMaximum(Qt.Vertical);
        size = (mw.web.page().viewportSize().height()/20);
        self.verticalScrollPosition = min(maxHeight, (self.verticalScrollPosition + size));
        mw.web.page().mainFrame().setScrollPosition(QPoint(0, self.verticalScrollPosition));
        
    # Define keyboard shortcuts for size up and size down. 
    #Note added Ctrl and '=' to avoid confusion when using standard keyboard (ie. without it, plus requires a shift, minus doesn't)
    def sizeAdjustSetupKeys(self):
        mw = self.mw;
        #Page up and page down, and arrow up and arrow down buttons implemented below
        if hasattr(mw, 'pgUp'):
            mw.pgUp.setEnabled(False);
            mw.disconnect(mw.pgUp, SIGNAL("activated()"), self.pageUpAction);
            mw.pgDown.setEnabled(False);
            mw.disconnect(mw.pgDown, SIGNAL("activated()"), self.pageDownAction);
            mw.arrowUp.setEnabled(False);
            mw.disconnect(mw.arrowUp, SIGNAL("activated()"), self.lineUpAction);
            mw.arrowDown.setEnabled(False);
            mw.disconnect(mw.arrowDown, SIGNAL("activated()"), self.lineDownAction);
        mw.pgUp = QShortcut(QKeySequence("PgUp"), mw);
        mw.connect(mw.pgUp, SIGNAL("activated()"), self.pageUpAction);
        mw.pgDown = QShortcut(QKeySequence("PgDown"), mw);
        mw.connect(mw.pgDown, SIGNAL("activated()"), self.pageDownAction);
        mw.arrowUp = QShortcut(QKeySequence("Up"), mw);
        mw.connect(mw.arrowUp, SIGNAL("activated()"), self.lineUpAction);
        mw.arrowDown = QShortcut(QKeySequence("Down"), mw);
        mw.connect(mw.arrowDown, SIGNAL("activated()"), self.lineDownAction);
        
        # create a size up and size down shortcuts and menu items
        if(self.sizeUpAction != None):
            mw.disconnect(self.sizeUpAction, SIGNAL("triggered()"), self.sizeUp);
            self.sizeUpAction.setEnabled(False);
            mw.form.menuEdit.removeAction(self.sizeUpAction);
            del self.sizeUpAction;
            mw.sizeUpShortcut.setEnabled(False);
            mw.sizeUpOnEqualShortcut.setEnabled(False);
            mw.disconnect(mw.sizeUpShortcut, SIGNAL("activated()"), self.sizeUp);
            mw.disconnect(mw.sizeUpOnEqualShortcut, SIGNAL("activated()"), self.sizeUp);
        mw.sizeUpShortcut = QShortcut(QKeySequence("Ctrl++"), mw);
        mw.sizeUpOnEqualShortcut = QShortcut(QKeySequence("Ctrl+="), mw);
        mw.connect(mw.sizeUpShortcut, SIGNAL("activated()"), self.sizeUp);
        mw.connect(mw.sizeUpOnEqualShortcut, SIGNAL("activated()"), self.sizeUp);
        self.sizeUpAction = QAction("Zoom In  (Ctrl++)", mw)
        mw.connect(self.sizeUpAction, SIGNAL("triggered()"), self.sizeUp)
        mw.form.menuEdit.addAction(self.sizeUpAction)
        
        if(self.sizeDownAction != None):
            mw.disconnect(self.sizeDownAction, SIGNAL("triggered()"), self.sizeDown);
            self.sizeDownAction.setEnabled(False);
            mw.form.menuEdit.removeAction(self.sizeDownAction);
            del self.sizeDownAction;
            mw.sizeDownShortcut.setEnabled(False);
            mw.disconnect(mw.sizeDownShortcut, SIGNAL("activated()"), self.sizeDown);
        mw.sizeDownShortcut = QShortcut(QKeySequence("Ctrl+-"), mw);
        mw.connect(mw.sizeDownShortcut, SIGNAL("activated()"), self.sizeDown);
        self.sizeDownAction = QAction("Zoom Out  (Ctrl+-)", mw)
        mw.connect(self.sizeDownAction, SIGNAL("triggered()"), self.sizeDown)
        mw.form.menuEdit.addAction(self.sizeDownAction)
        
        #quick keys dialog
        if(self.createShortcutMenuItem != None):
            mw.disconnect(self.createShortcutMenuItem, SIGNAL("triggered()"), self.showAddCardQuickKeysDialog);
            self.createShortcutMenuItem.setEnabled(False);
            mw.form.menuEdit.removeAction(self.createShortcutMenuItem);
            del self.createShortcutMenuItem;
            mw.quickKeys.setEnabled(False);
            mw.disconnect(mw.quickKeys, SIGNAL("activated()"), self.showAddCardQuickKeysDialog);
        mw.quickKeys = QShortcut(QKeySequence("Alt+1"), mw);
        mw.connect(mw.quickKeys, SIGNAL("activated()"), self.showAddCardQuickKeysDialog);
        menuItem = QAction("Create Add Cards shortcut (Alt+1)", mw);
        mw.connect(menuItem, SIGNAL("triggered()"), self.showAddCardQuickKeysDialog);
        mw.form.menuEdit.addAction(menuItem);
        self.createShortcutMenuItem = menuItem;
    
    def setDefaultDialogValues(self, keyModel):
        keyModel['deckName'] = None;
        keyModel['modelName'] = None;
        keyModel['fieldName'] = None;
        keyModel['ctrl'] = 'true';
        keyModel['shift'] = 'false';
        keyModel['alt'] = 'false';
        keyModel['keyName'] = None;
        keyModel['color'] = 'yellow'; 
        keyModel['colorText'] = 'true';
        keyModel['showEditor'] = 'true';
        keyModel['showEditCurrent'] = 'false';
        keyModel['enabled'] = 'true';
    
    def showAddCardQuickKeysDialog(self):
        #set values from lastDialogQuickKey or use default
        if(len(self.lastDialogQuickKey.keys()) < 1):
            self.setDefaultDialogValues(self.lastDialogQuickKey);
        
        d = QDialog(self.mw)
        l = QVBoxLayout()
        l.setMargin(0)
        w = AnkiWebView()
        l.addWidget(w)
        #Add python object to take values back from javascript
        quickKeyModel = QuickKeyModel();
        w.page().mainFrame().addToJavaScriptWindowObject("quickKeyModel", quickKeyModel);
        #deck combo box
        deckComboBox = "<span style='font-weight:bold'>Deck: </span><select id='decks'>";
        allDecks = mw.col.decks.all();
        allDecks.sort(key=lambda dck: dck['name'], reverse=False)
        for deck in allDecks:
            isSelected = '';
            if(self.lastDialogQuickKey.get('deckName', None) == deck['name']):
                isSelected = 'selected';
            deckComboBox = deckComboBox + ("<option value='" + str(deck['id']) + "' " + isSelected + ">" + deck['name'] + "</option>");
        deckComboBox = deckComboBox + "</select>";
        #model combo box
        fieldChooserByModel = {};
        modelComboBox = "<span style='font-weight:bold'>Model: </span><select id='models'>";
        allModels = mw.col.models.all();
        allModels.sort(key=lambda mod: mod['name'], reverse=False)
        for model in allModels:
            isSelected = '';
            if(self.lastDialogQuickKey.get('modelName', None) == model['name']):
                isSelected = 'selected';
            modelComboBox = modelComboBox + ("<option value='" + str(model['id']) + "' " + isSelected + ">" + model['name'] + "</option>");
            listOfFields = model['flds'];
            fieldComboBox = "";
            for field in listOfFields:
                fieldComboBox = fieldComboBox + ("<option value='" + field['name'] + "'>" + field['name'] + "</option>");
            fieldChooserByModel[str(model['id'])] = fieldComboBox;
        modelComboBox = modelComboBox + "</select>";
        
        ctrl = '';
        if(self.lastDialogQuickKey.get('ctrl', 1) == 1): ctrl = 'checked';
        shift = '';
        if(self.lastDialogQuickKey.get('shift', 0) == 1): shift = 'checked';
        alt = '';
        if(self.lastDialogQuickKey.get('alt', 0) == 1): alt = 'checked';
        
        #Ctrl checkbox
        ctrlCheckbox = "<span style='font-weight:bold'>Ctrl: </span><input type='checkbox' id='ctrl' " + ctrl + " />";
        #Shift checkbox
        shiftCheckbox = "<span style='font-weight:bold'>Shift: </span><input type='checkbox' id='shift' " + shift + "/>";
        #Alt checkbox
        altCheckbox = "<span style='font-weight:bold'>Alt: </span><input type='checkbox' id='alt' " + alt + "/>";
        
        #shortcut key combo box
        keyComboBox = "<span style='font-weight:bold'>Key: </span><select id='keys'>";
        isSelected = '';
        for val in range(0,10):
            if(str(val) == str(self.lastDialogQuickKey.get('keyName','0'))): isSelected = 'selected';
            keyComboBox = keyComboBox + ("<option value='" + str(val) + "' " + isSelected + ">" + str(val) + "</option>");
            isSelected = '';
        for code in range(ord('a'), ord('z')+1):
            if(str(chr(code)) == str(self.lastDialogQuickKey.get('keyName','0'))): isSelected = 'selected';
            keyComboBox = keyComboBox + ("<option value='" + chr(code) + "' " + isSelected + ">" + chr(code) + "</option>");
            isSelected = '';
        keyComboBox = keyComboBox + "</select>";
        #color text box
        colorValue = self.lastDialogQuickKey.get('color','yellow');
        colorTextField = "<span style='font-weight:bold'>Source highlighting color (IRead2 model only): </span><input type='text' id='color' value='" + colorValue + "' />";
        #radio buttons to chose if hilight or color text
        colorBackground = 'checked';
        colorText = '';
        if(self.lastDialogQuickKey.get('colorText', 'false') == 'true'):
            colorText = 'checked';
            colorBackground = '';
        colorBackOrText = "<span style='font-weight:bold'>Apply color to: &nbsp;</span><input type='radio' id='colorBackOrText' name='colorBackOrText' value='false' " + colorBackground + "/> Background &nbsp;&nbsp;<input type='radio' name='colorBackOrText' value='true' " + colorText + " /> Text<br />";
        #show editor checkbox
        doShowEditor = '';
        if(self.lastDialogQuickKey.get('showEditor', 1) == 1):
            doShowEditor = 'checked';
        showEditorCheckbox = "<span style='font-weight:bold'>Show Add Cards dialog?: </span><input type='checkbox' id='showEditor' " + doShowEditor + " />";
        #show current card editor checkbox
        doShowEditCurrent = '';
        if(self.lastDialogQuickKey.get('showEditCurrent', 0) == 1):
            doShowEditCurrent = 'checked';
        showEditCurrentCheckbox = "<span style='font-weight:bold'>Show Edit Current dialog?: </span><input type='checkbox' id='showEditCurrent' " + doShowEditCurrent + "/>";
        #remove shortcut checkbox
        doEnable = '';
        if(self.lastDialogQuickKey.get('enabled', 1) == 1):
            doEnable = 'checked';
        enabledCheckbox = "<span style='font-weight:bold'>Enable (uncheck to disable): </span><input type='checkbox' id='enabled' " + doEnable + " />";
        
        #javascript to populate field box based on selected model
        javascript = "var fieldsByModel = {};\n";
        for model in mw.col.models.all():
            listOfFields = model['flds'];
            javascript += "fieldsByModel['" + model['name'] + "'] = [";
            for field in listOfFields:
                javascript += "'" + re.escape(field['name']) + "',";
            javascript = javascript[:-1];
            javascript += "];\n";
        javascript += """
        function setFieldsForModel(mName) {
            var list = fieldsByModel[mName];
            var options = '';
            for(var i=0; i < list.length; i++) {
                var isSelected = '';
                if(list[i] == pasteToFieldValue) isSelected = 'selected';
                options += '<option value=\\'' + list[i] + '\\' ' + isSelected + '>' + list[i] + '</option>';
            }
            document.getElementById('fields').innerHTML = options;
        }
        """;
        javascript += "var pasteToFieldValue = '" + str(self.lastDialogQuickKey.get('fieldName', '')) + "';\n";
        html = "<html><head><script>" + javascript + "</script></head><body>";
        html += deckComboBox + "<p>";
        html += modelComboBox;
        html += "<p><span style='font-weight:bold'>Paste Text to Field: </span><select id='fields'>";
        html += fieldComboBox + "</select>";
        html += "<p><span style='font-weight:bold'>Key Combination:</span>&nbsp;&nbsp;" + ctrlCheckbox + "&nbsp;&nbsp;" + shiftCheckbox + "&nbsp;&nbsp;" + altCheckbox + "&nbsp;&nbsp;" + keyComboBox;
        #html += "<p>" + keyComboBox;
        html += "<p>" + colorTextField;
        html += "<p>" + colorBackOrText;
        html += "<p>" + showEditorCheckbox;
        html += "<p>" + showEditCurrentCheckbox;
        html += "<p>" + enabledCheckbox;
        html += "</body></html>";
        #print html;
        w.stdHtml(html);
        #Dynamically add the javascript hook to call the setFieldsForModel function
        addHooksScript = """
        document.getElementById('models').onchange=function() {
            var sel = document.getElementById('models'); 
            setFieldsForModel(sel.options[sel.selectedIndex].text);
        };
        function getValues() {
            var sel = document.getElementById('decks'); 
            quickKeyModel.setDeck(sel.options[sel.selectedIndex].text);
            sel = document.getElementById('models'); 
            quickKeyModel.setModel(sel.options[sel.selectedIndex].text);
            sel = document.getElementById('fields'); 
            quickKeyModel.setField(sel.options[sel.selectedIndex].text);
            sel = document.getElementById('ctrl'); 
            quickKeyModel.setCtrl(sel.checked);
            sel = document.getElementById('shift'); 
            quickKeyModel.setShift(sel.checked);
            sel = document.getElementById('alt'); 
            quickKeyModel.setAlt(sel.checked);
            sel = document.getElementById('keys'); 
            quickKeyModel.setKey(sel.options[sel.selectedIndex].text);
            quickKeyModel.setSourceHighlightColor(document.getElementById('color').value.trim());
            sel = document.getElementById('colorBackOrText'); 
            if(sel.checked) {
                quickKeyModel.setColorText('false');
            } else {
                quickKeyModel.setColorText('true');
            }
            sel = document.getElementById('showEditor'); 
            quickKeyModel.setShowEditor(sel.checked);
            sel = document.getElementById('showEditCurrent'); 
            quickKeyModel.setShowEditCurrent(sel.checked);
            sel = document.getElementById('enabled'); 
            quickKeyModel.setEnabled(sel.checked);
        };
        //Set the fields for the selected model
	    var sel = document.getElementById('models'); 
        setFieldsForModel(sel.options[sel.selectedIndex].text);
        """
        w.eval(addHooksScript);
        bb = QDialogButtonBox(QDialogButtonBox.Close|QDialogButtonBox.Save)
        bb.connect(bb, SIGNAL("accepted()"), d, SLOT("accept()"))
        bb.connect(bb, SIGNAL("rejected()"), d, SLOT("reject()"))
        bb.setOrientation(QtCore.Qt.Horizontal);
        l.addWidget(bb)
        d.setLayout(l)
        d.setWindowModality(Qt.WindowModal)
        d.resize(700, 500)
        choice = d.exec_();
        
        w.eval("getValues()");
        #move values to a map so they can be serialized to file later (Qt objects don't pickle well)
        keyModel = {};
        keyModel['deckName'] = quickKeyModel.deckName;
        keyModel['modelName'] = quickKeyModel.modelName;
        keyModel['fieldName'] = quickKeyModel.fieldName;
        
        #Ctrl + Shift + Alt + Key
        ctrl = 0;
        if(quickKeyModel.ctrl == 'true'): ctrl = 1;
        keyModel['ctrl'] = ctrl;
        shift = 0;
        if(quickKeyModel.shift == 'true'): shift = 1;
        keyModel['shift'] = shift;
        alt = 0;
        if(quickKeyModel.alt == 'true'): alt = 1;
        keyModel['alt'] = alt;
        keyModel['keyName'] = quickKeyModel.keyName;
        
        keyModel['color'] = quickKeyModel.color; 
        keyModel['colorText'] = quickKeyModel.colorText;
        doShowEditor = 0;
        if(quickKeyModel.showEditor == 'true'): 
            doShowEditor = 1;
        keyModel['showEditor'] = doShowEditor;
        doShowEditCurrent = 0;
        if(quickKeyModel.showEditCurrent == 'true'): 
            doShowEditCurrent = 1;
        keyModel['showEditCurrent'] = doShowEditCurrent;
        keyModel['enabled'] = 1 if (quickKeyModel.enabled) else 0;
        #Save the last selected values in the dialog for later use
        self.lastDialogQuickKey = keyModel;
        #If SAVE chosen, then save the model as a new shortcut
        if(choice == 1):
            self.setQuickKey(keyModel);
            
    def setQuickKey(self, keyModel):
        keyCombo = '';
        if(keyModel['ctrl'] == 1): keyCombo += "Ctrl+";
        if(keyModel['shift'] == 1): keyCombo += "Shift+";
        if(keyModel['alt'] == 1): keyCombo += "Alt+";
        keyCombo += keyModel['keyName'];
        
        existingKeyModel = self.quickKeys.get(keyCombo, None); 
        if(existingKeyModel != None):
            self.quickKeys.pop(keyCombo, None);
            if(existingKeyModel.get('transient', None) != None):
                shortcut = existingKeyModel['transient'].get('shortcut');
                mw.disconnect(shortcut, SIGNAL("activated()"), existingKeyModel['transient'].get('callable'));
                shortcut.setEnabled(False);
                del shortcut;
                menuItem = existingKeyModel['transient'].get('menuItem');
                mw.disconnect(menuItem, SIGNAL("activated()"), existingKeyModel['transient'].get('callable'));
                menuItem.setEnabled(False);
                mw.form.menuEdit.removeAction(menuItem);
                del menuItem;
        if(keyModel['enabled'] == 1): 
            shortcut = QShortcut(QKeySequence(keyCombo), mw);
            callMe = lambda: self.quickAddCards(keyModel);
            mw.connect(shortcut, SIGNAL("activated()"), callMe);
            #add menu item showing defined shortcut
            menuText = "[Add Cards] " + keyModel['modelName'] + " -> " + keyModel['deckName'] + " (" + keyCombo + ")";
            hColor = keyModel.get('color', None);
            if(hColor != None and len(hColor) > 0): menuText += " [" + hColor + "]";
            else: keyModel['color'] = None;
            menuItem = QAction(menuText, mw);
            mw.connect(menuItem, SIGNAL("triggered()"), callMe);
            mw.form.menuEdit.addAction(menuItem);
            keyModel['transient'] = {'shortcut':shortcut,'callable':callMe, 'menuItem':menuItem};
            self.quickKeys[keyCombo] = keyModel;
            self.savePluginData();
        #    _saveShortcut(self.db, keyModel);
        #else:
        #    _deleteShortcut(self.db, keyModel);
        
    def quickAddCards(self, quickKeyModel):
        self.saveScrollPosition();
        hasSelection = 0;
        selectedText = '';
        #Copy text or html to clipboard if selected, else just use clipboard contents (user could hit Ctrl-C in a web browser instead)
        if(len(mw.web.selectedText()) > 0): 
            hasSelection = 1;
            mw.web.triggerPageAction(QWebPage.Copy);
            clipboard = QApplication.clipboard();
            mimeData = clipboard.mimeData();
            selectedText = mimeData.html();
            #Highlight the text in the original document. This is only useful for cards with long texts like IRead2. Other card models will ignore.
            if(quickKeyModel.get('color', None) != None): 
                runHook("highlightText", quickKeyModel['color'], quickKeyModel.get('colorText', 'false'));
            
        #Create new note with selected model and deck  
        new_model = mw.col.models.byName(quickKeyModel['modelName'])      
        new_note = notes.Note(mw.col, new_model)
        self.setField(new_note, quickKeyModel['fieldName'], selectedText)
        
        #Add tags and copy source fields from source card, if applicable
        if(mw.reviewer.card):
            card = mw.reviewer.card
            cur_note = card.note()
            tags = cur_note.stringTags();
            new_note.setTagsFromStr(tags); #sets tags for the note, but still have to set them in the editor if show dialog (see below)

            SOURCE_FIELD_NAME = 'Source'
            TITLE_FIELD_NAME = 'Title'
            self.setField(new_note, SOURCE_FIELD_NAME, self.getField(cur_note, SOURCE_FIELD_NAME))
            self.setField(new_note, TITLE_FIELD_NAME, self.getField(cur_note, TITLE_FIELD_NAME))

            #This is very specific to IRead2 Model and should be generalized or moved elsewhere
            IREAD_MODEL_NAME = 'IRead2'
            TEXT_FIELD_NAME = 'Text'
            SOURCE_FIELD_NAME = 'Source'
            DECK_FIELD_NAME = 'Anki Deck'
            MODEL_FIELD_NAME = 'Model'
            if(mw.reviewer.card.model()['name'] == IREAD_MODEL_NAME):
                for f in new_model['flds']:
                    if(SOURCE_FIELD_NAME == f['name']):
                        self.setField(new_note, SOURCE_FIELD_NAME, self.getField(cur_note, SOURCE_FIELD_NAME))
                #if(quickKeyModel['modelName'] == IREAD_MODEL_NAME):
    #                self.setField(new_note, SOURCE_FIELD_NAME, self.getField(cur_note, SOURCE_FIELD_NAME))
                #    self.setField(new_note, MODEL_FIELD_NAME, self.getField(cur_note, MODEL_FIELD_NAME))
                #    self.setField(new_note, DECK_FIELD_NAME, self.getField(cur_note, DECK_FIELD_NAME))
                
        #If shortcut said NOT to show AddCards dialog, then skip it.
        if(quickKeyModel['showEditor'] == 0):
            if(hasSelection == 1):
                new_note.model()['did'] = mw.col.decks.byName(quickKeyModel['deckName'])['id'];
                ret = new_note.dupeOrEmpty()
                if ret == 1:
                    showWarning(_(
                        "The first field is empty."),
                        help="AddItems#AddError")
                    return
                cards = mw.col.addNote(new_note)
                if not cards:
                    showWarning(_("""\
                        The input you have provided would make an empty \
                        question on all cards."""), help="AddItems")
                    return
                # stop anything playing
                clearAudioQueue()
                mw.col.autosave()
                tooltip(_("Added"), period=500)  
        #Else show the add cards dialog
        else:
            self.acsCount += 1;
            if(quickKeyModel['showEditCurrent'] == 1): self.editCurrent = editcurrent.EditCurrent(mw);
            self.addCards = addcards.AddCards(mw)
            self.addCards.editor.setNote(new_note)
            if(new_note.stringTags() != None): self.addCards.editor.tags.setText(new_note.stringTags().strip()); #Not sure why doesn't get set automatically since note has associated tags, but ...
            self.addCards.modelChooser.models.setText(quickKeyModel['modelName'])
            self.addCards.deckChooser.deck.setText(quickKeyModel['deckName'])
            
    
    def setField(self, note, name, content):
        ord = mw.col.models.fieldMap(note.model())[name][0]
        note.fields[ord] = content
        return note

    def getField(self, note, name):
        ord = mw.col.models.fieldMap(note.model())[name][0]
        return note.fields[ord]

    #Invoked when profile loaded
    def loadPluginData(self): 
        # Remove quickKeys if already loaded (ie. handle for switching profile instead of just restart anki)
        if(len(self.quickKeys) > 0):
            self.removeQuickKeys();
            
        # Add key handlers and menu items
        self.sizeAdjustSetupKeys();
        
        # File to persist data
        self.dataDir = self.mw.pm.profileFolder() + '/collection.media';
        self.dataFilename = self.dataDir + '/_ViewSizeAdjustAddon.dat';
        #self.db = mw.col.db;
        #_addSchema(self.db);
        #self.quickKeys = _loadShortcuts(self.db);
        loadedQuickKeys = {};
        if(os.path.isfile(self.dataFilename)):
            f = open(self.dataFilename, "r")
            tmp = f.read()
            if(tmp):
                try:
                    pluginData = pickle.loads(tmp);
                    multiplier = pluginData.get('textSizeMultiplier', 1);
                    self.lastDialogQuickKey = pluginData.get('lastDialogQuickKey', {});
                    if(multiplier > -1):
                        self.textSizeMultiplier = multiplier;
                        self.mw.web.setTextSizeMultiplier(self.textSizeMultiplier);
                    loadedQuickKeys = pluginData['quickKeys'];
                except:
                    print "error reading pluginData file";
                    pass;
            f.close();
        self.addQuickKeys(loadedQuickKeys);
    
    def removeQuickKeys(self):
        for qkey in self.quickKeys.keys():
            quickKey = self.quickKeys.get(qkey, None);
            if(quickKey != None): 
                quickKey['enabled'] = 0;
                self.setQuickKey(quickKey);
    
    def addQuickKeys(self, mapOfQuickKeys):
        for qkey in mapOfQuickKeys.keys():
            quickKey = mapOfQuickKeys.get(qkey, None);
            if(quickKey != None): 
                #Set reasonable defaults for legacy shortcuts that did not previously support ctrl, shift, alt, showEditCurrent
                if(quickKey.get('ctrl', None) == None): quickKey['ctrl'] = 1;
                if(quickKey.get('shift', None) == None): quickKey['shift'] = 0;
                if(quickKey.get('alt', None) == None): quickKey['alt'] = 0;
                if(quickKey.get('showEditCurrent', None) == None): quickKey['showEditCurrent'] = 0;
                if(quickKey.get('showEditor', None) == None): quickKey['showEditor'] = 1;
                if(quickKey.get('enabled', None) == None): quickKey['enabled'] = 1;
                self.setQuickKey(quickKey);
            else: print "qkey not found: " + str(qkey);
    
    def savePluginData(self):
        quickKeysCopy = {}
        for qkey in self.quickKeys.keys():
            quickKey = self.quickKeys.get(qkey, None);
            if(quickKey != None): 
                quickKeysCopy[qkey] = quickKey.copy();
                quickKeysCopy[qkey]['transient'] = None;
        lastDialogQuickKeyCopy = self.lastDialogQuickKey.copy();
        lastDialogQuickKeyCopy['transient'] = None;
        # File to persist plugin data
        pluginData = {'textSizeMultiplier':self.textSizeMultiplier,'quickKeys':quickKeysCopy,'lastDialogQuickKey':lastDialogQuickKeyCopy}
        tmp = pickle.dumps(pluginData);
        f = open(self.dataFilename, "w")
        f.write(tmp)
        f.close();
        #touch the media folder to force sync
        st = os.stat(self.dataDir);
        atime = st[ST_ATIME] #access time
        mtime = st[ST_MTIME] #modification time
        new_mtime = time.time(); #new modification time
        os.utime(self.dataDir,(atime,new_mtime))
        
    #Add schema to support storing IRead2 data relative to selections, cards created, last position in any card, etc.
    def _addSchema(db):
        db.executescript("""
        create table if not exists ire_addcards_shortcuts (
            key             text primary key,
            deck            text not null,
            model           text not null,
            field           text not null,
            show_editor     bool not null
        );

        create table if not exists ire_card_info (
            card_id              integer primary key,   
            scroll_position      integer not null,         
            zoom_factor          float not null      
        );
        """);

    def _loadShortcuts(db):
        cur = db.execute("""
        select key, deck, model, field, show_editor
            from ire_addcards_shortcuts
        """);
        keys = {};
        if(cur != None):
            rows = cur.fetchall();
            for row in rows:
                print 'found key: ' + row[0];
                keyModel = {};
                keyModel['deckName'] = row[1];
                keyModel['modelName'] = row[2];
                keyModel['fieldName'] = row[3];
                keyModel['keyName'] = row[0];
                keyModel['showEditor'] = row[4];
                keyModel['enabled'] = 1;
                keyModel['persisted'] = 1;
                keys[row[0]] = keyModel;
        else: 
            print 'no shortcuts found in database';
            cur = db.execute("""
                select count(*) from ire_addcards_shortcuts;
                """);
            print cur.fetchone()[0];
        return keys;

    def _saveShortcut(db, quickKey):
        if(quickKey != None): 
            if(quickKey.get('persisted',None) == None):
                sql = "insert into ire_addcards_shortcuts (key, deck, model, field, show_editor) values('" + quickKey['keyName'] + "','" + quickKey['deckName'] + "','" + quickKey['modelName'] + "','" + quickKey['fieldName'] + "'," + str(quickKey['showEditor']) + ")";
                print sql;
                db.execute(sql);
            else:
                sql = "update ire_addcards_shortcuts set key='" + quickKey['keyName'] + "', deck='" + quickKey['deckName'] + "', model='" + quickKey['modelName'] + "', field='" + quickKey['fieldName'] + "', show_editor=" + str(quickKey['showEditor']) + " where key='" + quickKey['keyName'] + "'";
                print sql;
                db.execute(sql);
            cur = db.execute("""
                select count(*) from ire_addcards_shortcuts;
                """);
            print cur.fetchone()[0];

    def _deleteShortcut(db, quickKey):
        if(quickKey != None): 
            if(quickKey.get('persisted',None) != None):
                sql = "delete from ire_addcards_shortcuts where key='" + quickKey['keyName'] + "'";
                print sql;
                db.execute(sql);
            
class QuickKeyModel(QtCore.QObject):  
    deckName = '';
    modelName = '';
    fieldName = '';
    ctrl = True;
    shift = False;
    alt = False;
    keyName = '';
    color = 'yellow';
    colorText = 'false';
    showEditor = True;
    enabled = True;
    @QtCore.pyqtSlot(str)
    def setDeck(self, deck):  
        self.deckName = deck; 
    @QtCore.pyqtSlot(str)
    def setModel(self, model):  
        self.modelName = model;
    @QtCore.pyqtSlot(str)
    def setField(self, field):  
        self.fieldName = field;
    @QtCore.pyqtSlot(str)
    def setCtrl(self, shouldShow):  
        self.ctrl = shouldShow;
    @QtCore.pyqtSlot(str)
    def setShift(self, shouldShow):  
        self.shift = shouldShow;
    @QtCore.pyqtSlot(str)
    def setAlt(self, shouldShow):  
        self.alt = shouldShow;
    @QtCore.pyqtSlot(str)
    def setKey(self, key):  
        self.keyName = key;
    @QtCore.pyqtSlot(str)
    def setSourceHighlightColor(self, color): 
        self.color = color;
    @QtCore.pyqtSlot(str)
    def setColorText(self, colorText): 
        self.colorText = colorText;
    @QtCore.pyqtSlot(str)
    def setShowEditor(self, shouldShow):  
        self.showEditor = shouldShow;
    @QtCore.pyqtSlot(str)
    def setShowEditCurrent(self, shouldShow):  
        self.showEditCurrent = shouldShow;
    @QtCore.pyqtSlot(str)
    def setEnabled(self, isEnabled): 
        self.enabled = (isEnabled == 'true');
        
mw.viewManager = ViewManager(mw);
addHook("profileLoaded", mw.viewManager.loadPluginData); #Why does addHook require loadSizePreference with no braces (), whereas wrap requires sizeAdjustSetupKeys with braces?
addHook('unloadProfile', mw.viewManager.savePluginData);

# Dangerous: We are monkey patching a method beginning with _
# Added these next two monkey patches (resetRequiredState and reviewState) 
# to prevent reviewer from advancing to next card when using AddCards shortcuts.
def vsa_resetRequiredState(self, oldState, _old):
    #print "vsa_resetRequiredState: acsCount=" + str(self.viewManager.acsCount) + ", mw.reviewer.card=" + str(mw.reviewer.card) + ", and old state =" + oldState;
    specialHandling = False;
    if(self.viewManager.acsCount - self.viewManager.rrsCount == 1):
        specialHandling = True;
    self.viewManager.rrsCount = self.viewManager.acsCount;
    if (specialHandling and mw.reviewer.card):
        if oldState == "resetRequired":
            #print "vsa_resetRequiredState: Doing reset required with 'review'";
            return _old(self, 'review');
        else:
            #print "vsa_resetRequiredState: Doing reset required with old state: " + oldState;
            return _old(self, oldState);
        return;
    else: 
        #print "vsa_resetRequiredState: Requisite conditions not met. Delegating to original resetRequiredState method.";
        return _old(self, oldState);
    
def vsa_reviewState(self, oldState, _old):
    #print "vsa_reviewState: acsCount=" + str(self.viewManager.acsCount) + ", mw.reviewer.card=" + str(mw.reviewer.card) + ", and old state =" + oldState;
    specialHandling = False;
    if(self.viewManager.acsCount - self.viewManager.rsCount == 1):
        specialHandling = True;
    self.viewManager.rsCount = self.viewManager.acsCount;
    if (specialHandling and "review" == oldState):
        self.col.reset();
        curNote = self.reviewer.card.note();
        self.web.setHtml(curNote['Text']);
        self.reviewer.bottom.web.show();
        self.IRead2.adjustZoomAndScroll();
    else: 
        #print "vsa_reviewState: Requisite conditions not met. Delegating to original reviewState method.";
        return _old(self, oldState);       
AnkiQt._resetRequiredState = wrap(AnkiQt._resetRequiredState, vsa_resetRequiredState, "around")
AnkiQt._reviewState = wrap(AnkiQt._reviewState, vsa_reviewState, "around")