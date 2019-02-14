## HipChat Export Instructions for LonoCloud

### Create an API token

* Go to https://coa.hipchat.com/account/api
* Login using your hipchat (non-ViaSat account), i.e.
  USER@lonocloud.com. It will likely ask for you to confirm your
  password a second time. You should now be at the "API Access" space.
* Click "View Group" and "View Messages" scopes (permissions) in the
  drop-down (i.e. select them together using Ctrl click).
* Give this new token an arbitrary name (e.g. "backup") and click
  Create.
* Copy/save the personal token string shown at the top of the page.
  You will need this to use the export script.

### Checkout this project

```
git clone git@github.com:LonoCloud/hipchat_export.git
cd hipchat_export
```

### List the personal chats

Use the script to list all 1x1 chats that you have participated in
(the PERSONAL\_TOKEN is the string/token from above):

```
./hipchat-export -u PERSONAL_TOKEN -l
```

This will output two columns with the name of the user in the left
column and the ID of that user on the right:

```
The following users are active and will be queried for 1-to-1
messages:

Name                 ID
----------------------------
Jane Doe             123
Joe Smith            456
...
```

### Download selected 1x1 Chats

From the user list above, create a comma separated list
of the 1x1 user IDs that you wish to save/export. Use this list to
save/export the 1x1 chats with all media files:

```
./hipchat-export -u PERSONAL_TOKEN --extract_users=123,456,789
```

You can download just the textual messages by adding the `--messages`
flag:

```
./hipchat-export -u PERSONAL_TOKEN --extract_users=123,456,789 --messages
```

The result of running the command above will be a subdirectory named
`hipchat_export/USER/` containing JSON data in files name 0.txt,
1.txt, etc (with up to 100 messages per file).


### Download all 1x1 Chats

Collect all the 1x1 chat IDs into a comma separated variable:

```
IDS=$(echo $(./hipchat-export.py -u PERSONAL_TOKEN -l | grep -o '[0-9][0-9]*$') | sed 's/ /,/g')
```

Use that variable to download just the text messages for all chats:

```
./hipchat-export.py -u PERSONAL_TOKEN --extract_users="${IDS}" --messages
```

Downloading all my (Joel Martin) 1x1 chats messages (without media
files) took XYZ seconds. The reason for this is that the API itself is
not particularly fast and the export API is throttled and so the
script has to pause periodically.

