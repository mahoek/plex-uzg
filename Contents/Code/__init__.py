'''
Created on May 08, 2009

@summary: A Plex Media Server plugin that integrates Uitzending Gemist videos into Plex
@version: 0.3
@author: Matthijs.H
'''

#import from python

import re, datetime, base64, urllib2, string, os, sys

# Import the parts of the Plex Media Server Plugin API we need

from PMS import Plugin, Log, DB, Thread, XML, HTTP, JSON, RSS, Utils
from PMS.MediaXML import MediaContainer, DirectoryItem, SearchDirectoryItem, VideoItem
from PMS.Shorthand import _L, _R, _E, _D

UZG_PLUGIN_PREFIX  = "/video/uzgnl"

UZG_ROOT_URI       = "http://www.uitzendinggemist.nl/"

UZG_TOP_50         = UZG_ROOT_URI + "index.php/top50"
UZG_TODAY          = UZG_ROOT_URI + "index.php/selectie?searchitem=dag&dag=vandaag"
UZG_YESTERDAY      = UZG_ROOT_URI + "index.php/selectie?searchitem=dag&dag=gisteren"
UZG_NED_ONE        = UZG_ROOT_URI + "index.php/selectie?searchitem=net_zender&net_zender=1"
UZG_NED_TWO        = UZG_ROOT_URI + "index.php/selectie?searchitem=net_zender&net_zender=2"
UZG_NED_THREE      = UZG_ROOT_URI + "index.php/selectie?searchitem=net_zender&net_zender=3"
UZG_NED_ZAPP       = UZG_ROOT_URI + "index.php/selectie?searchitem=omroep&omroep=47"
UZG_SEARCH_TITLE   = UZG_ROOT_URI + "index.php/search?sq=%s&search_filter=titel"

UZG_PLAYER_URI        = "http://player.omroep.nl/"
UZG_PLAYER_INIT_FILE  = UZG_PLAYER_URI + "js/initialization.js.php"
UZG_PLAYER_META       = UZG_PLAYER_URI + "xml/metaplayer.xml.php"

#UZG_DAY_REGEX       = '<a class="title" href="/index.php/serie(\?serID=\d+&amp;md5=[^"]+)">([^<]+)</a></td>\W+<td align="right">([^<]+)</td>'
#UZG_TOP_REGEX       = r"""<td style=[^>]+><a href="/index.php/aflevering(\?aflID=\d+&amp;md5=[^"]+)">([^<]+)</a></td>\W+<td align="right">([^<]+)</td>"""

UZG_REGEX_PAGE_ITEM2       = r"""<a href="http://player.omroep.nl/(\?aflID=\d+)"[^>]+><img .*? alt="bekijk uitzending: ([^\"]+)" />"""
UZG_REGEX_SEARCH_ITEM      = r"""<a class="title" href="/index.php/search(\?serID=\d+&amp;md5=[^&]+)&sq=[^\"]+">([^<]+)</a>"""
UZG_REGEX_PAGE_ITEM        = r"""<a class="title" href="/index.php/serie(\?serID=\d+&amp;md5=[^\"]+)">([^<]+)</a>"""
UZG_REGEX_PAGE_PAGES       = r"""class="populair_top_pagina_nr">(\d+)</(a|strong)>"""
#UZG_REGEX_PAGE_INFO       = r"""<td><a class=\"title\" href=\"/index.php/serie?\?serID=(\d+&amp;md5=[0-9a-f]+)\">%s</a></td>"""

#UZG_REGEX_TEMP = r"""<a href="http://player.omroep.nl/(\?aflID=\d+&amp;md5=[0-9a-f]+)\""""

UZG_REGEX_POPULAR_SECTION  = r"""<thead id=\"tooltip_populair\"([\w\W]+)<script type=\"text/javascript\">"""
UZG_REGEX_POPULAR_ITEM     = r"""<td><a href=\"/index.php/aflevering(\?aflID=\d+&amp;md5=[0-9a-f]+)\">([^<]+)</a></td>\W+<td [^>]+>([^<]+)</td>"""

UZG_REGEX_TIPS_SECTION     = r"""<div id=\"tooltip_moetjezien\"([\w\W]+)<script type=\"text/javascript\">"""
UZG_REGEX_TIPS_ITEM        = r"""<a href=\"/index.php/aflevering(\?aflID=\d+&amp;md5=[0-9a-f]+)\" class=\"title\">([^<]+)</a>"""

UZG_REGEX_ITEM_SECURITY    = r"""var securityCode = '([0-9a-f]+)'"""
UZG_REGEX_ITEM_INFO        = r"""<b class="btitle">[^<]+</b>\s+<p style="margin-top:5px;">(.*?)(\s+<)"""
UZG_REGEX_ITEM_THUMB       = r"""<td height="100" style="padding-right:20px;">\s+<img src="(.*?)" .*? style="float:left;margin:0px 5px 0px 0px;" />"""

UZG_REGEX_STREAM_URI       = r"""<stream[^>]+compressie_kwaliteit=.bb.[^>]+compressie_formaat=.wmv.[^>]*>([^<]*)</stream>"""
UZG_REGEX_STREAM_DIRECT    = r"""<Ref href[^"]+"([^"]+)\""""

CACHE_INTERVAL      = 3600

def Start():
  Plugin.AddRequestHandler(UZG_PLUGIN_PREFIX, HandleRequest, "Uitzending Gemist", "icon-default.jpg", "art-default.jpg")
  Plugin.AddViewGroup("Main", viewMode="List", contentType="items")
  Plugin.AddViewGroup("Items", viewMode="InfoList", contentType="items")
  temp = urllib2.urlopen(UZG_ROOT_URI).read() #get NOS cookies

def HandleRequest(pathNouns, count):
  try:
    title2 = pathNouns[count-1].replace("_", " ").encode('utf-8')
  except:
    title2 = ""
 
  dir = MediaContainer('art-default.jpg', "Main", title1 = "Uitzending Gemist", title2 = title2)
  dir.SetAttr("content", "items")
  
  Log.Add("Count: " + str(count))
  Log.Add("pathNouns: " + str(pathNouns))
  
  if count == 0:
    dir.AppendItem(DirectoryItem("Populair", "Populair", Plugin.ExposedResourcePath('icon-default.jpg')))
    dir.AppendItem(DirectoryItem("Zenders", "Zenders", Plugin.ExposedResourcePath('icon-default.jpg')))
    dir.AppendItem(DirectoryItem("Genres", "Genres", Plugin.ExposedResourcePath('icon-default.jpg')))
    dir.AppendItem(DirectoryItem("Omroepen", "Omroepen", Plugin.ExposedResourcePath('icon-default.jpg')))
    dir.AppendItem(DirectoryItem("Vandaag", "Vandaag", Plugin.ExposedResourcePath('icon-default.jpg')))
    dir.AppendItem(DirectoryItem("Gisteren", "Gisteren", Plugin.ExposedResourcePath('icon-default.jpg')))
    dir.AppendItem(SearchDirectoryItem("Zoeken", "Zoeken", "Zoeken in Uitzending Gemist", Plugin.ExposedResourcePath('icon-default.jpg')))
  elif count > 0 and pathNouns[0] == 'Populair':
    if count == 1:
      dir.AppendItem(DirectoryItem("Most_viewed", "Meest bekeken vandaag", Plugin.ExposedResourcePath('icon-default.jpg')))
      dir.AppendItem(DirectoryItem("Moet_je_zien", "Moet je zien", Plugin.ExposedResourcePath('icon-default.jpg')))
      dir.AppendItem(DirectoryItem("Top_50", "Top 50 afgelopen dagen", Plugin.ExposedResourcePath('icon-default.jpg')))
    elif count == 2:
      if pathNouns[1] == 'Top_50':
        data = HTTP.GetCached(UZG_TOP_50, CACHE_INTERVAL).decode('latin-1')
        listSectionItems(dir, data, UZG_REGEX_PAGE_ITEM2)
      elif pathNouns[1] == 'Most_viewed':
        listSection(dir, UZG_ROOT_URI, UZG_REGEX_POPULAR_ITEM, UZG_REGEX_POPULAR_SECTION)
      elif pathNouns[1] == 'Moet_je_zien':
        listSection(dir, UZG_ROOT_URI, UZG_REGEX_TIPS_ITEM, UZG_REGEX_TIPS_SECTION)
  elif count > 0 and pathNouns[0] == 'Genres':
    if count == 1:
      genres = [['Amusument', '1'], ['Animatie', '2'], ['Comedy', '3'], ['Documantaire', '4'], ['Drama', '21'], ['Educatief', '24'], ['Erotiek', '5'], ['Film', '6'], ['Gezondheid', '27'], ['Informatief', '7'], ['Jeugd', '8'], ['Kinderen 2-5', '25'], ['Kinderen 6-12', '26'], ['Klassiek', '23'], ['Kunst & Cultuur', '9'], ['Maatschappij', '19'], ['Misdaad', '10'], ['Muziek', '11'], ['Natuur', '12'], ['Nieuws & Actualiteiten', '13'], ['Overige', '14'], ['Religieus', '15'], ['Serie & Soap', '16'], ['Sport', '17'], ['Wetenschap', '18']]
      for e in genres:
        dir.AppendItem(DirectoryItem("%s/%s" % (e[1], e[0]), e[0], Plugin.ExposedResourcePath('icon-default.jpg')))
    elif count == 3:
      listPages(dir, 'http://www.uitzendinggemist.nl/index.php/selectie?searchitem=genre&genre=%s' % (pathNouns[1]), UZG_REGEX_PAGE_ITEM)
  elif count > 0 and pathNouns[0] == 'Omroepen':
    if count == 1:
      genres = [['3FM', '33'], ['AVRO', '11'], ['BNN', '16'], ['BOS', '7'], ['EO', '15'], ['HUMAN', '29'], ['IKON', '3'], ['Joodse Omroep', '48'], ['KRO', '2'], ['LLiNK', '45'], ['MAX', '46'], ['MTNL', '52'], ['NCRV', '8'], ['Nederland 1', '55'], ['Nederland 2', '56'], ['NIO', '49'], ['NMO', '4'], ['NOS', '12'], ['NPS', '22'], ['OHM', '5'], ['Omrop Fryslan', '6'], ['Radio 4', '27'], ['RKK', '1'], ['RNW', '25'], ['RVU', '23'], ['TELEAC & NOT', '43'], ['TROS', '14'], ['Vara', '17'], ['VPRO', '20'], ['Z@PP', '37'], ['Z@ppelin', '19'], ['ZvK', '28']]
      for e in genres:
        dir.AppendItem(DirectoryItem("%s/%s" % (e[1], e[0]), e[0], Plugin.ExposedResourcePath('icon-default.jpg')))
    elif count == 3:
      listPages(dir, 'http://www.uitzendinggemist.nl/index.php/selectie?searchitem=omroep&omroep=%s' % (pathNouns[1]), UZG_REGEX_PAGE_ITEM)
  elif count > 0 and pathNouns[0] == 'Zenders':
    if count == 1:
      dir.AppendItem(DirectoryItem("Nederland_1", "Nederland 1", Plugin.ExposedResourcePath('icon-ned1.jpg')))
      dir.AppendItem(DirectoryItem("Nederland_2", "Nederland 2", Plugin.ExposedResourcePath('icon-ned2.jpg')))
      dir.AppendItem(DirectoryItem("Nederland_3", "Nederland 3", Plugin.ExposedResourcePath('icon-ned3.jpg')))
      dir.AppendItem(DirectoryItem("Z@PP", "Z@PP", Plugin.ExposedResourcePath('icon-zapp.jpg')))
    elif count == 2:
      if pathNouns[1] == 'Nederland_1':
        listPages(dir, UZG_NED_ONE, UZG_REGEX_PAGE_ITEM)
      if pathNouns[1] == 'Nederland_2':
        listPages(dir, UZG_NED_TWO, UZG_REGEX_PAGE_ITEM)
      if pathNouns[1] == 'Nederland_3':
        listPages(dir, UZG_NED_THREE, UZG_REGEX_PAGE_ITEM)
      if pathNouns[1] == 'Z@PP':
        listPages(dir, UZG_NED_ZAPP, UZG_REGEX_PAGE_ITEM)
  elif pathNouns[0] == 'Vandaag':
    listPages(dir, UZG_TODAY, UZG_REGEX_PAGE_ITEM)
  elif pathNouns[0] == 'Gisteren':
    listPages(dir, UZG_YESTERDAY, UZG_REGEX_PAGE_ITEM)
  elif pathNouns[0] == 'Gisteren':
    listPages(dir, UZG_YESTERDAY, UZG_REGEX_PAGE_ITEM)
  elif pathNouns[0] == 'Zoeken':
    if count > 1:
      query = pathNouns[1].replace(" ","%20")
      listPages(dir, (UZG_SEARCH_TITLE % (query)), UZG_REGEX_SEARCH_ITEM)
  elif pathNouns[0] == 'play':
    url = getStreamUrl(pathNouns[1])
    #return Plugin.Redirect(url)
    dir.AppendItem(VideoItem(url, "Speel aflevering af", "", "", ""))
    #dir.AppendItem(VideoItem("mms://tempo01.omroep.nl/nos_journaal24-bb", "Zoek oudere afleveringen", "", "", ""))
  elif pathNouns[0] == 'list':
    dir = MediaContainer('art-default.jpg', "Items", title1 = "Uitzending Gemist", title2 = title2)
    dir.SetAttr("content", "items")
    listShowItems(dir, urllib2.urlopen(UZG_ROOT_URI + "index.php/serie" + base64.b64decode(pathNouns[1])).read().decode('latin-1'), UZG_REGEX_PAGE_ITEM2, pathNouns[2])
    listShowItems(dir, urllib2.urlopen(UZG_ROOT_URI + "index.php/serie2" + base64.b64decode(pathNouns[1])).read().decode('latin-1'), UZG_REGEX_PAGE_ITEM2, pathNouns[2])

  return dir.ToXML()

def getStreamUrl(path):
  temp = HTTP.Get("%s%s" % (UZG_PLAYER_URI, base64.b64decode(path)), 3600)
  site = HTTP.Get("%s%s" % (UZG_PLAYER_INIT_FILE, base64.b64decode(path)), 3600)
  code = re.search(UZG_REGEX_ITEM_SECURITY, site).group(1)
  url = "%s%s&md5=%s" % (UZG_PLAYER_META, base64.b64decode(path), code)
  item_url = re.search(UZG_REGEX_STREAM_URI, urllib2.urlopen(url).read()).group(1)
  return re.search(UZG_REGEX_STREAM_DIRECT, urllib2.urlopen(item_url).read()).group(1)

def listShows(dir, data, regex):
  results = re.compile(regex, re.DOTALL + re.IGNORECASE + re.M).findall(data)
  if len(results) > 0:
    for result in results:
      dir.AppendItem(DirectoryItem(UZG_PLUGIN_PREFIX + "/list/" + base64.b64encode(result[0], "_;") + "/" + result[1], result[1], Plugin.ExposedResourcePath('icon-default.jpg')))
  else:
    dir.AppendItem(DirectoryItem(UZG_PLUGIN_PREFIX, 'Er konden geen series/afleveringen worden gevonden', Plugin.ExposedResourcePath('icon-default.jpg')))

def listShowItems(dir, data, regex, title):
  info = re.compile(UZG_REGEX_ITEM_INFO, re.DOTALL + re.IGNORECASE + re.M).search(data)
  thumb = re.compile(UZG_REGEX_ITEM_THUMB, re.DOTALL + re.IGNORECASE + re.M).search(data)
  results = re.compile(regex, re.DOTALL + re.IGNORECASE + re.M).findall(data)
  
  try:
    if thumb.group(1):
      thumbUri = thumb.group(1)
  except:
    thumbUri = ''
  
  for result in results:
    dir.AppendItem(DirectoryItem(UZG_PLUGIN_PREFIX + "/play/" + base64.b64encode(result[0], "_;") + "/" + result[1], result[1], thumbUri, info.group(1).replace("\n", "").strip()))

def listSection(dir, url, regex, regex_section):
  data = urllib2.urlopen(url).read().decode('latin-1')
  result = re.compile(regex_section, re.DOTALL + re.IGNORECASE).findall(data)
  listSectionItems(dir, result[0], regex)

def listSectionItems(dir, data, regex):
  results = re.compile(regex, re.DOTALL + re.IGNORECASE + re.M).findall(data)
  for result in results:
    dir.AppendItem(DirectoryItem(UZG_PLUGIN_PREFIX + "/play/" + base64.b64encode(result[0], "_;") + "/" + result[1], result[1], Plugin.ExposedResourcePath('icon-default.jpg')))

def listPages(dir, url, regex):
  data = HTTP.Get(url).decode('latin-1')
  data = data.replace("<span class=\"highlight\">", "").replace("</span>", "")

  result = re.compile(UZG_REGEX_PAGE_PAGES, re.DOTALL + re.IGNORECASE).findall(data)
  if len(result) > 0:
    for e in result:
      #listShows(dir, urllib2.urlopen('%s&pgNum=%s' % (url, e[0])).read().decode('latin-1'), regex)
      listShows(dir, HTTP.GetCached('%s&pgNum=%s' % (url, e[0]), CACHE_INTERVAL).decode('latin-1'), regex)
  else:
    listShows(dir, data, regex)