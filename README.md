# Installation

This document assumes you've followed the directions at
https://www.zabbix.com/download?zabbix=2.2&os_distribution=centos&os_version=7&db=MySQL
for a CentOS 7 installation. It applies to Zabbix version 2.2 but 2.4+
should be quite similar as well.

Determine where your `AlertScriptsPath` is. By default on the CentOS
7/Zabbix 2.2 installation, it's in `/usr/lib/zabbix/alertscripts`.

Copy send_signifai.py directly into that directory and `chmod 0755` it.

# Configuration

## 1. Creating the media type
1. Enter the Administration page from the top tabs of the screen
2. Click "Media types" from the bar just under the top tabs of
   the screen
3. Click the "Create media type" button on the far right side of the
   screen under the History bar.
4. Enter "signifai" as the name
5. Change "Type" to "Script"
6. Set "Script name" to `send_signifai.py`
7. Make sure Enabled is checked
8. Click the Save button

## 2. Creating the SignifAI user and user group
1. Make sure you're in the Administration tab
2. Enter the Users section (it's the link immediately to the left of
   "Media Types")
3. Click the "Create user group" button on the far right side of the
   screen, just to the right of the selection box saying "User groups"
4. Set "signifai" as the Group name. Ensure that the Frontend access
   selection box is set to Disabled and that the Enabled checkbox is
   checked, and click into the Permissions tab. 
5. Click the "Add" button underneath the list box in the Read only column.
6. Check everything in the popup. (The SignifAI user must have at least
    read access to everything to get notifications)
7. Once everything is selected, click the Save button at the bottom of
   the page. 
8. Now change the "User groups" in the selection box on the right
   to "Users".
9. Click the "Create user" button to the right of that selection box
10. Fill Alias with "signifai", _choose a strong password_ and fill 
    the password fields with it, and fill everything else out at your 
    discretion.
11. Add the "signifai" user group to the Groups list by using the Add 
    button just to the right of the list box. A pop-up should appear;
    check the box for "signifai" and click Select. The pop-up should
    close.
12. Click the "Media" tab.
13. Click "Add" under the media list (which should say "No media found."
    at this point)
14. In the popup, change the type to "signifai"
15. Put "signifai" in the "Send to" field. 
16. If it isn't already, ensure that "When active" is set to 1-7,00:00-24:00
17. Make sure all checkboxes for "Use if severity" are checked
18. Ensure that "Status" is "Enabled"
19. Click the "Add" button in the pop-up. The new media should be added
    to the media list.
20. Click the "Save" button at the bottom of the page.

## 3. Adding the reporting action
1. Enter the Configuration page from the top tabs of the screen
2. Click into the "Actions" sub-section (it usually winds up being
   just under the Administration tab)
3. Ensure "Event source" on the right side of the screen is set to
   "Triggers", and then click the "Create Action" button above it
4. Set Name to "Notify SignifAI", Default Subject to your bugsnag key,
   and Default Message to the following:

   ```
   TRIGGER.DESCRIPTION: {TRIGGER.DESCRIPTION}
   TRIGGER.ID: {TRIGGER.ID}
   TRIGGER.NAME: {TRIGGER.NAME}
   TRIGGER.NSEVERITY: {TRIGGER.NSEVERITY}
   HOST.NAME: {HOST.NAME}
   TRIGGER.STATUS: {TRIGGER.STATUS}
   TRIGGER.EXPRESSION: {TRIGGER.EXPRESSION}
   EVENT.DATE: {EVENT.DATE}
   EVENT.TIME: {EVENT.TIME}
   _API_KEY: <YOUR API KEY>
   ```
5. Check Recovery message, set Recovery subject the same as Default
   subject and set Recovery message to the following:

   ```
   TRIGGER.DESCRIPTION: {TRIGGER.DESCRIPTION}
   TRIGGER.ID: {TRIGGER.ID}
   TRIGGER.NAME: {TRIGGER.NAME}
   TRIGGER.NSEVERITY: {TRIGGER.NSEVERITY}
   HOST.NAME: {HOST.NAME}
   TRIGGER.STATUS: {TRIGGER.STATUS}
   TRIGGER.EXPRESSION: {TRIGGER.EXPRESSION}
   EVENT.DATE: {EVENT.RECOVERY.DATE}
   EVENT.TIME: {EVENT.RECOVERY.TIME}
   _API_KEY: <YOUR API KEY>
   ```
6. Ensure "Enabled" is checked
7. Enter the Conditions tab; ensure that the conditions are "Maintenance
   status not in _Maintenance_" and "Trigger value = _PROBLEM_"
8. Enter the Operations tab. There should be no operations defined. Click 
   the New link beneath the empty list.
9. Change the "To" field to 0 (to allow notification forever)
10. Add the "signifai" user to "Send to Users"
11. Click the "Add" link under the form to add it to the operations list.
12. Click the "Save" button at the bottom of the page.