import argparse
import json
import jsons
from datetime import datetime
import dateutil.parser
import time
import pytz
import os
import sys
import requests

from nixapi_web import NixPlay
from nixapi_mobile import NixPlayMobile
from colorama import Fore, Back, Style, init

try:
    init()
except:
    print('No colour support')

def format_flickr_photos_for_nixplay(photos):
  items = { "items": [] }
  for photo in photos['photoset']['photo']:
    updated = datetime.fromtimestamp(int(photo["lastupdate"]))
    orientation = 1 if photo["width_o"] < photo["height_o"] else 0
  
    items['items'].append({ 
      "photoUrl":     photo["url_k"] if "url_k" in photo else photo["url_o"], 
      "thumbnailUrl": photo["url_m"],
      "orientation":  orientation
    })

  return items

def delete_playlist_photo_range(np, playlist_id, offset, count):
  while offset < count:
    photos = np.getPlayListSlides(playlist_id, offset, min(count, 30))    
    ids = [p['playlistItemId'] for p in photos['slides']]

    r = np.delPlayListPhotos(playlist_id, ids)
    offset += min(count, 30)

def update_nixplay_playlist_from_flickr_album(np, np_playlist_name, flickr_album_name, force):
 
  # Nixplay playlist
  playlist = np.getPlayList(np_playlist_name)  
  if not playlist:
    print(f'Playlist not found: {np_playlist_name}')
    return 1
  #print(json.dumps(playlist, indent=2))
  #utcfromtimestamp

  np_picture_count = playlist['picture_count']
  np_last_updated = dateutil.parser.isoparse(playlist['last_updated_date'])
  
  #np_last_updated = datetime.utcfromtimestamp(np_last_updated)#int(playlist['last_updated_date']))
  #np_last_updated = utc.localize(np_last_updated)
  print(f'Nixplay ({np_playlist_name}) - {np_picture_count} photos - updated: {np_last_updated}')


  # Flickr album
  photoset = np.flickr_photosets_getWithName(flickr_album_name)
  #print(json.dumps(photoset, indent=2))

  # Album info
  #info = np.flickr_photosets_getInfo(photoset['id'])
  #print(json.dumps(info, indent=2))

  flickr_last_updated = datetime.fromtimestamp(int(photoset['date_update']), pytz.timezone("UTC"))
  #flickr_last_updated = utc.localize(flickr_last_updated)
  print(f'Flickr ({flickr_album_name}) - {photoset["count_photos"]} photos - updated: {flickr_last_updated}')

  if np_last_updated < flickr_last_updated or force: 

    if force:
      print('Forced update!')
    
    print(f'Updating: flickr[{flickr_album_name}] -> nixplay[{np_playlist_name}]')

    # delete all but 1 image from the nixplay playlist
    if np_picture_count > 1:
      delete_playlist_photo_range(np, playlist['id'], 1, np_picture_count - 1)
      np_picture_count = 1

    # process photos 1 page at a time
    for page in range(0, -(-photoset['count_photos']//30)):
      photos = np.flickr_photosets_getPhotos(photoset['id'], page+1, 30)
      items = format_flickr_photos_for_nixplay(photos)

      items["items"].reverse()
      r = np.addPlayListPhotos(playlist['id'], items)
      code=requests.status_codes._codes[r.status_code][0]
      print(f'Posted {len(items["items"])} photos ({code})')

    # delete the remaining image
    delete_playlist_photo_range(np, playlist['id'], 0, np_picture_count)

    print('Done')
  else:
    print('Nothing to do')

def status(np):
  frames = np.getFrames()
  print(json.dumps(frames, indent=2))
  print('-'*80)

  for frame in frames:
    config = np.getFrameSettings(frame['id'])
    print(json.dumps(config, indent=2))
  
  print('-'*80)
  
  status = np.getOnlineStatus()
  print(json.dumps(status, indent=2))
  
  for frame in status['frames']:
    ls = datetime.fromtimestamp(int(frame['lastConnected'])/100)
    print(f'lastSeen: {ls}')


#
# if the frame is playing the specified playlist, then start it off again
#
def update_nixplay_frame_with_playlist(npm, frame_name, playlist_name, np):
  frame = npm.getFrame(frame_name)  
  playlist = npm.getPlayList(playlist_name)

  for pl in frame['playlists']:
    if pl['id'] == playlist['id']:
      print('starting playlist')
      r = npm.startPlaylist(frame['id'], playlist['id'])
      print(json.dumps(r, indent=2))


def main(args):

  # login to Web api
  np = NixPlay()
  np.login(args.username, args.password)

  # login to Mobile api
  npm = NixPlayMobile()
  npm.login(args.username, args.password)

  if args.status:
    status(np)
    return 0

  if args.start:
    update_nixplay_frame_with_playlist(npm, args.frame, args.playlist, np)
    return 0

  while True:

    update_nixplay_playlist_from_flickr_album(np, args.playlist, args.album, args.force)
    #update_nixplay_frame_with_playlist(npm, args.frame, args.playlist, np)

    if not args.poll:
      break

    time.sleep(args.poll)

if __name__ == "__main__":
  parser = argparse.ArgumentParser('Nixplay / Flickr album sync')
  parser.add_argument('--username', help='Nixplay username')
  parser.add_argument('--password', help='Nixplay password')
  parser.add_argument('--frame', dest = 'frame', default='Westcott')
  parser.add_argument('--nixplay-list', dest = 'playlist', default='My Playlist')
  parser.add_argument('--flickr-album', dest = 'album', default='Favs')
  parser.add_argument('--poll', type=int, default = 0)
  parser.add_argument('--force',  action='store_true', default=False)
  parser.add_argument('--status', action='store_true', default=False)
  parser.add_argument('--start',  action='store_true', default=False)

  args = parser.parse_args()
  if not args.username and 'NIXPLAY_USERNAME' in os.environ:
    args.username = os.environ['NIXPLAY_USERNAME']
  else:
    print('Missing username')
    sys.exit(-1)

  if not args.password and 'NIXPLAY_PASSWORD' in os.environ:
    args.password = os.environ['NIXPLAY_PASSWORD']
  else:
    print('Missing password')
    sys.exit(-1)    

  main(args)


