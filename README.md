* [License](#license)
* [Installation](#installation)
* [Configuration](#configuration)
   * [2.2+](#22)
      * [1. Creating the media type](#1-creating-the-media-type)
      * [2. Creating the SignifAI user and user group](#2-creating-the-signifai-user-and-user-group)
      * [3. Adding the reporting action](#3-adding-the-reporting-action)
   * [3.X](#3X)
      * [1. Creating the media type](#1-creating-the-media-type-1)
      * [2. Creating the user group and user](#2-creating-the-user-group-and-user)
      * [3. Creating the notification action](#3-creating-the-notification-action)

# License

This project is licensed under Apache Software License version 2. Please see
LICENSE for details.

# Installation

This document assumes you've followed the directions at
https://www.zabbix.com/download?zabbix=2.2&os_distribution=centos&os_version=7&db=MySQL
for a CentOS 7 installation. It applies to Zabbix version 2.2 but 2.4+
should be quite similar as well.

Determine where your `AlertScriptsPath` is. By default on the CentOS
7/Zabbix 2.2 installation, it's in `/usr/lib/zabbix/alertscripts`. The
same is true for Zabbix 3.4.

Copy send_signifai.py directly into that directory and `chmod 0755` it.

# Configuration

## 2.2+

### 1. Creating the media type
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

### 2. Creating the SignifAI user and user group
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

### 3. Adding the reporting action
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

## 3.X

### 1. Creating the media type

1. Click the Administration link at the very top of the page to pop up a link
   bar beneath it; enter the "Media types" subsection by clicking its link
   in that bar.
2. Click the "Create media type" button near the upper right corner of
   the page.
3. In the media type form, give the name "signifai", change the Type
   to "Script", use the Script name "send_signifai.py", and click the Add
   link in the Script parameters box three times to get three empty text
   boxes; in those three text boxes, put `{ALERT.SENDTO}`, `{ALERT.SUBJECT}`
   and `{ALERT.MESSAGE}`, in that order. Ensure that Enabled is checked, then
   hit the Add button.

### 2. Creating the user group and user

1. Click the User groups link, two to the left of Media types in the
   Administration section.
2. Click the "Create user group" button near the upper right corner of
   the page.
3. For the Group name, enter "signifai". Set Frontend access to Disabled,
   and ensure the Enabled checkbox is checked. Then, click into the 
   Permissions tab above the form.
4. Click the "Select" button to the right of the text box saying "type here to
   search". You will be presented a pop-up with a list of host groups with 
   check boxes next to them. Click the check box at the top in the column 
   header next to "Name" to check all of the host groups, and then click the 
   Select button just after the list to save the selection and dismiss the 
   popup. Click the "Read" button to the right of the groups box to allow
   read access to the groups, check the Include subgroups box, then click the
   Add link below Include subgroups.
5. Click the Add button at the bottom of the create user group page. You 
   should be taken back to the User groups page, and signifai should be in the
   list now.
6. Enter the Users subsection by clicking the link to the right of the User 
   groups link.
7. Click the Create user button at the top right of the screen.
8. In the User form, set Alias to "signifai". Add the group we just created by
   typing "signifai" into the Groups text box and pressing enter. Choose a 
   strong password and enter it into the password boxes, and set the Language
   to English (en_US).
9. Switch to the Media tab by clicking to the link to the right of User above 
   the form. Click the Add link at the bottom of the Media table to get a
   popup; in that popup, choose "signifai" for the Type, enter "signifai" in
   the "Send to" field, ensure that "When active" is "1-7,00:00-24:00", that
   all of the "Use if severity" check boxes and the Enabled check box are
   checked. Then click Add to save the changes and dismiss the popup. The 
   media should now show up in the table.
10. Click the Add button beneath the Media table to add the signifai user.

### 3. Creating the notification action

1. Click the Configuration link at the top of the page, then in the link bar
   that pops up underneath it, click the Actions link to enter the Actions
   subsection.
2. Click the Create Action button near the upper right corner of the page.
3. Set the Name to "Notify SignifAI", then switch into the Operations tab.
4. Change "Default subject" to your bugsnag key and "Default message" to the
   following:

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
5. Click the "New" link in the Operations table to expand the Operation 
   details form. Change the second text box for "Steps" to 0 to have the same
   operation continue indefinitely. Click the "Add" link in the Send to Users
   box to get a pop-up with a list of users and check the box next to
   "signifai", then click Select to add the user and dismiss the popup. Click
   the Add link at the bottom of the Operation details form to add the
   operation.
6. Enter the "Recovery operations" screen by clicking the link to the right
   of Operations. Again, put the bugsnag key in the "Default subject" box,
   then put this template as the "Default message":

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

   Repeat step 5 to add the signifai user to notifications for recoveries as 
   well.
7. Click the Add button at the bottom of the page to add this action and hook
   Zabbix notifications up to SignifAI.

