#!/etc/anaconda2/bin/python

from __future__ import print_function
import httplib2
import shutil
import os
import bs4
import time
import sys
import json
from hashlib import md5 
from datetime import datetime

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from gdata import gauth
import gdata.photos, gdata.photos.service

try:
  import argparse
  flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
  flags = None

### GLOBALS ###

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/drive-python-quickstart.json
SCOPES = 'https://picasaweb.google.com/data/ https://www.googleapis.com/auth/drive'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Personal Photo Sync'

PHOTO_ALBUM = "6316489518140194977"
VIDEO_ALBUM = "0B5QT17osW5Emc1NnUEJHRUtONEU"
SOURCE_DIRS = ["/media/dan/disk/DCIM/",
               "/media/dan/disk/PRIVATE/AVCHD/BDMV/STREAM/"]
STAGING_DIR = os.path.join(os.path.expanduser("~"), "staging")
MASTERS_DIR = "/media/wdmycloud/HomeShare/Photos/masters"

def get_credentials():
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'photosync.json')

    store = Storage(credential_path)
    credentials = store.get()

    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def list_albums(http_client):
  (resp_headers, content) = http_client.request("https://picasaweb.google.com/data/feed/api/user/default", "GET")
  soup = bs4.BeautifulSoup(content, 'lxml')
  for e in soup.html.body.feed:
    id_soup = e.find("gphoto:id")
    name_soup = e.find("gphoto:name")
    num_soup = e.find("gphoto:numphotos")
    title_soup = e.find("media:title")
    print("%s - %s - %s - %s" % ("" if id_soup == None else id_soup.string, 
                       "" if title_soup == None else title_soup.string,
                       "" if name_soup == None else name_soup.string,
                       "" if num_soup == None else num_soup.string))

def post_photo(http_client, album_id, filepath):
  slug = os.path.basename(filepath)
  content_type = 'image/jpeg' 

  print("Loading image into memory... %s" % (filepath))
  with open(filepath,'rb') as fh:
    data = fh.read()
  url = "https://picasaweb.google.com/data/feed/api/user/default/albumid/%s" % (album_id)
  print("POSTing %s to %s" % (slug, url))
  (resp_headers, content) = http_client.request(url, method="POST", body=data, headers={'Content-Type':content_type,'Slug':slug})
  print("Finished upload")
  
  if "status" in resp_headers:
    if resp_headers["status"] == '201':
      return True

  print("====POST ERROR===")
  print(resp_headers)
  print(content)
  print("=================")
  raise Exception("Error occurred while posting")

def post_photo_multipart(http_client, album_id, filepath):
  slug = os.path.basename(filepath)
  content_type = 'image/jpeg' 

  print("Loading file into memory... %s" % (filepath))
  with open(filepath,'rb') as fh:
    data = fh.read()

  createdTime = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime(os.path.getmtime(filepath)))

  boundary="foo_bar_baz"
  url = "https://picasaweb.google.com/data/feed/api/user/default/albumid/%s" % (album_id)

 # metadata = {"name": slug, 
 #             "mimeType": content_type, 
 #             "parents": [ album_id ], 
 #             "createdTime": createdTime,
 #             "modifiedTime": createdTime}
  metadata = """
<entry xmlns='http://www.w3.org/2005/Atom'> 
  <title>%s</title> 
  <category scheme="http://schemas.google.com/g/2005#kind" 
            term="http://schemas.google.com/photos/2007#photo"/> 
  <updated>%s</updated> 
  <published>%s</published> 
</entry>""" % (slug, createdTime, createdTime)
  #print(metadata)

  post_data = [
      '--%s' % boundary,
      'Content-Type: application/atom+xml',
      '',
      metadata,
      '--%s' % boundary,
      'Content-Type: %s' % content_type,
      '',
      data,
      '--%s--' % boundary 
  ]
  
  post_body = '\n'.join(post_data)

  headers = {"Content-Type":"multipart/related; boundary=%s" % boundary, 
             "Content-Length":len(post_body),
             "MIME-version":1.0}
  (resp_headers, content) = http_client.request(url, method='POST', headers=headers, body=post_body)
  print("Finished upload")
  
  if "status" in resp_headers:
    if resp_headers["status"] == '201':
      return True

  print("====POST ERROR===")
  print(resp_headers)
  print(content)
  print("=================")
  raise Exception("Error occurred while posting")


def post_video_multipart(http_client, album_id, filepath):
  slug = os.path.basename(filepath)
  content_type = "video/vnd.mts"

  print("Loading video into memory... %s" % (filepath))
  with open(filepath,'rb') as fh:
    data = fh.read()

  createdTime = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime(os.path.getmtime(filepath)))

  boundary="foo_bar_baz"
  url = "https://www.googleapis.com/upload/drive/v3/files/?uploadType=multipart"

  metadata = {"name": slug, 
              "mimeType": content_type, 
              "parents": [ album_id ], 
              "createdTime": createdTime,
              "modifiedTime": createdTime}
  print(json.dumps(metadata, indent=2))

  post_data = [
      '--%s' % boundary,
      'Content-Type: application/json; charset=UTF-8',
      '',
      json.dumps(metadata),
      '',
      '--%s' % boundary,
      'Content-Type: %s' % content_type,
      '',
      data,
      '--%s--' % boundary 
  ]
  
  post_body = '\n'.join(post_data)

  headers = {"Content-Type":"multipart/related; boundary=%s" % boundary, "Content-Length":len(post_body)}
  (resp_headers, content) = http_client.request(url, method='POST', headers=headers, body=post_body)
  print("Finished upload")
  
  if "status" in resp_headers:
    if resp_headers["status"] == '200':
      return True

  print("====POST ERROR===")
  print(resp_headers)
  print(content)
  print("=================")
  raise Exception("Error occurred while posting")

def find(name, path):
    for root, dirs, files in os.walk(path):
        if name in files:
            return os.path.join(root, name)
    return None
    
def stage():
    source_dirs = SOURCE_DIRS
    target_dir = STAGING_DIR
    print("Pulling files off the media card")
    if not os.path.exists(target_dir):
      raise Exception("ERROR Directory not found: %s" % target_dir)

    known_files = set(get_all_known_files())

    for frompath in source_dirs:
     if os.path.exists(frompath):

      for subdir, dirs, files in os.walk(frompath):
       print(">>>> Processing files in: %s" % (subdir))
       for file in sorted(files):
         filepath = os.path.join(subdir,file)
         filesize = os.stat(filepath).st_size 
         (basefilename, fileextn) = os.path.splitext(file)
         newfn = "%s_%i%s" % (basefilename, filesize, fileextn)
         newpath = os.path.join(target_dir,newfn)
         if newfn in known_files:
           print("Skipping file: %s -> %s" % (file,newfn)) 
         else:
           shutil.copy2(filepath, newpath)
           if os.path.exists(newpath):
             print("file %s staged successfully..." % file)
           else:
             print("Copy seems to have failed...\n%s  ->  %s" % (filepath, newpath))
     else:
       print("Looks like media card not mounted")

def main(stg=True, proc=True ):
    print("SOURCE_DIRS: %s" % ",".join(SOURCE_DIRS))
    print("STAGING_DIR: %s" % STAGING_DIR)
    print("MASTERS_DIR: %s" % MASTERS_DIR)

    ### Check that target directory is mounted correctly, should be 3.5TB
    if os.statvfs(MASTERS_DIR).f_blocks/1024.0/1024.0/1024.0 < 3.0:
      raise Exception("WD MyCloud does not seem to be mounted.")

    ### copy media off of camera card
    if stg:
      print("Staging...")
      stage()
  
    ### Send to masters and google
    if proc:
      print("Processing...")
      process()

def process():
    ### process all files residing in staging directory
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    
    #get_albums(http_client=http)
    #get_photos(http_client=http, album_id=ALBUM)
    
    frompath = STAGING_DIR

    if not os.path.exists(frompath):
      raise Exception("ERROR Directory not found: %s" % frompath)

    print(">>> BEGIN  PROCESSING PHOTOS <<<")
    print("  >> %s <<" % str(datetime.now()))
    print("Processing files in %s..." % (frompath))

    for subdir, dirs, files in os.walk(frompath):
      print(">>>> Processing files in: %s" % (subdir))
      for file in sorted(files):
        print("  >> %s <<" % str(datetime.now()))

        filepath = subdir + os.sep + file

        dt = time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(filepath)))
        newdir = MASTERS_DIR + os.sep + dt
        newpath = newdir + os.sep + file
        chk = find(file, MASTERS_DIR)
        if chk:
          print("File already exists in masters: %s" % (chk))
        else:
          print("  Posting to Google: %s" % (newpath))

          #Post to google photos
          credentials.refresh(http)

          if filepath.lower().endswith(('.jpg', '.jpeg')):
            post_photo_multipart(http, PHOTO_ALBUM, filepath) 
            #post_photo(http, PHOTO_ALBUM, filepath) 
          elif filepath.lower().endswith(('.mts')):
            post_video_multipart(http, VIDEO_ALBUM, filepath)
          else:
            print("====POST ERROR===")
            print("  Invalid file type: %s" % (filepath))
            raise Exception("Invalid file type")

          #move to masters file share
          print("  moving file to masters: %s" % (newpath))
          if not os.path.exists(newdir):
            print("Creating date directory: %s" % newdir)
            os.makedirs(newdir)

          print("moving %s to %s" % (filepath, newdir))
#          os.rename(filepath, newpath)
          shutil.copy2(filepath, newpath)
          if os.path.exists(newpath):
            os.remove(filepath)
            print("Move successful...")
          else:
            "Copy seems to have failed...\n%s  ->  %s" % (filepath, newpath)
            raise Exception("ERROR Copy failed...")

    print(">>> FINISHED PROCESSING PHOTOS <<<")

    print(">>> BEGIN DELETE EMPTY DIRECTORIES <<<")
    print("  >> %s <<" % str(datetime.now()))
    for subdir, dirs, files in os.walk(frompath):
        if os.path.samefile(subdir, frompath):
            pass
        elif len(dirs) == 0 and len(files) == 0:
            print("  >>> Deleting empty directory: %s" % (subdir))
            os.rmdir(subdir)
        else:
            print("  >>> Cannot delete because files still exist: %s" % (subdir) )
        
    print(">>> FINISHED DELETING DIRECTORIES <<<")

def get_all_known_files():
  all_files = []
  for subdir, dirs, files in os.walk(MASTERS_DIR):
    all_files.extend(files)
  return all_files

if __name__ == '__main__':
    main(stg=True, proc=True)
