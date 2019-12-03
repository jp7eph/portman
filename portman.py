#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright Naoki.H
# 
# jp7eph@gmail.com

import re
import os
import sys
import time
import socket
import curses
import locale
import signal
from optparse import OptionParser

# Python3 doesn't have commands module anymore
# Python2 already has subprocess, but Python2's
# subprocess doesn't provide getoutput
try:
    from commands import getoutput
except ImportError:
    from subprocess import getoutput

# Python3 provides the lowlevel threading api
# which Python2 exposed as _thread
try:
    import thread
except ImportError:
    import _thread as thread

locale.setlocale(locale.LC_ALL, "en_US.UTF-8")

TITLE_PROGNAME = "PORT MAN"
TITLE_VERSION = "[ver 0.1]"
TITLE_VERTIC_LENGTH = 4

try :
    TITLE_HOSTINFO = "From: %s (%s)" % (
        getoutput ("hostname"),
        socket.gethostbyname (getoutput ("hostname")))
except :
    TITLE_HOSTINFO = "From: %s" % getoutput ("hostname")

ARROW = " > "
REAR  = "   "
REQ_INTERVAL = 0.05
REQ_ALLTARGET_INTERVAL = 5
MAX_HOSTNAME_LENGTH = 20
MAX_URL_LENGTH = 40
RESULT_STR_LENGTH = 10

DEFAULT_COLOR = 1
UP_COLOR = 2
DOWN_COLOR = 3

CONFIGFILE = "portman.conf"

OSNAME = getoutput ("uname -s")

REQ_SUCCESS     = 0
REQ_FAILED      = -1
REQ_TIMEOUT     = -2

REQ_TIMEOUT_SEC = 5

class RequestResult :

    def __init__ (self, success = False, errcode = REQ_FAILED) :
        self.success = success
        self.errcode = errcode
        return


class RequestTarget :

    def __init__ (self, name, url, port) :

        self.name = name
        self.url = url
        self.port = port
        self.state = False
        self.loss = 0
        self.lossrate = 0.0
        self.snt = 0 # number of sent requests
        self.result = []

        self.request = Request (self.url, self.port)

        return
    def __eq__ (self, other) :
        return str(self) == str(other)

    def send (self) :
        res = self.request.send()

        self.snt += 1

        if res.success :
            # Request Success
            self.state = True
        
        else :
            # Request Failed
            self.loss += 1
            self.state = False

        self.lossrate = float (self.loss) / float (self.snt) * 100.0
        self.result.insert (0, self.get_result_char (res))

        while len (self.result) > RESULT_STR_LENGTH :
            self.result.pop()

    def get_result_char (self, res) :

        if res.errcode == REQ_TIMEOUT :
            # Requst timeout
            return "t"

        if res.errcode == REQ_FAILED :
            # Request failed
            return "X"

        return "O"

    def refresh (self) : 
        self.state = False
        self.lossrate = 0.0
        self.loss = 0
        self.snt = 0
        self.result = []

        return


class Request :

    def __init__ (self, url, port, timeout = REQ_TIMEOUT_SEC) : 

        self.url = url
        self.port = port
        self.tout = timeout

        return

    def send (self) : 

        res = RequestResult()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(self.tout)
            try:
                s.connect((self.url, int(self.port)))
                res.success = True
                res.errcode = REQ_SUCCESS
            except socket.timeout as err:
                res.success = False
                res.errcode = REQ_TIMEOUT
            except OSError as err:
                res.success = False
                res.errcode = REQ_FAILED

        return res


class CursesCtrl () :

    def __init__ (self, stdscr) :
        self.stdscr = stdscr
        return

    def key_thread (self, *args) :

        while True :
            ch = self.stdscr.getch ()

            if ch == ord ('r') :
                num = 0
                for target in args :
                    num += 1
                    target.refresh()
                    self.erase_requesttarget(num)
                    self.print_requesttarget(target, num)

    def update_info (self, targets) :
        # update start point and string length

        self.y, self.x = self.stdscr.getmaxyx()

        # update arrow
        self.start_arrow = 0
        self.length_arrow = len(ARROW)

        # update hostname
        hlen = len ("HOSTNAME ")
        for target in targets :
            if hlen < len (target.name) : hlen = len (target.name)
        if hlen > MAX_HOSTNAME_LENGTH : hlen = MAX_HOSTNAME_LENGTH

        self.start_hostname = self.start_arrow + self.length_arrow
        self.length_hostname = hlen

        # update url
        alen = len ("URL:PORT ")
        for target in targets :
            if alen < len (target.url + target.port) : alen = len (target.url + target.port)
        if alen > MAX_URL_LENGTH : alen = MAX_URL_LENGTH
        else : alen += 5

        self.start_url = self.start_hostname + self.length_hostname + 1
        self.length_url = alen

        # update reference
        self.ref_start = self.start_url + self.length_url + 1
        self.ref_length = len (" LOSS  SNT")

        # update result
        self.res_start = self.ref_start + self.ref_length + 2
        self.res_length = self.x - (self.ref_start + self.ref_length + 2)

        # reverse
        if self.res_length < 10 :
            rev = 10 - self.res_length + len (ARROW)
            self.ref_start -= rev
            self.res_start -= rev
            self.res_length = 10

        global RESULT_STR_LENGTH
        RESULT_STR_LENGTH = self.res_length

        return


    def refresh (self) :

        self.stdscr.refresh ()
        return

    def waddstr (self, *args) :

        # wrapper for stdscr.addstr

        try :
            if len (args) == 3 :
                self.stdscr.addstr (args[0], args[1], args[2])
            if len (args) > 3 :
                self.stdscr.addstr (args[0], args[1], args[2], args[3])
        except curses.error :
            pass

    def print_title (self) :

        # Print Program name on center of top line
        spacelen = int ((self.x - len (TITLE_PROGNAME)) / 2)
        self.waddstr (0, spacelen, TITLE_PROGNAME, curses.A_BOLD)

        # Print hostname and version number
        self.waddstr (1, self.start_hostname, TITLE_HOSTINFO,
                            curses.A_BOLD)
        spacelen = self.x - (len (ARROW) + len (TITLE_VERSION))
        self.waddstr (1, spacelen, TITLE_VERSION, curses.A_BOLD)
        self.waddstr (2, len (ARROW),
                            "Keys: (r)efresh")
        self.stdscr.move (0, 0)
        self.stdscr.refresh ()
        return

    def erase_title (self) :
        space = ""
        for x in range (self.x) :
            space += " "
        self.waddstr (0, 0, space)
        self.waddstr (1, 0, space)
        self.waddstr (2, 0, space)
        return

    def print_reference (self) :
        hostname_str = "HOSTNAME"
        url_str = "URL:PORT"
        values_str = " LOSS  SNT  RESULT"

        # Print reference hostname and address
        self.waddstr (TITLE_VERTIC_LENGTH, len (ARROW),
                      hostname_str, curses.A_BOLD)
        self.waddstr (TITLE_VERTIC_LENGTH, self.start_url,
                      url_str, curses.A_BOLD)

        # Print references of values
        self.waddstr (TITLE_VERTIC_LENGTH, self.ref_start,
                      values_str, curses.A_BOLD)

        self.stdscr.move (0, 0)
        self.stdscr.refresh ()
        return

    def erase_reference (self) :
        space = ""
        for x in range (self.x) :
            space += " "
        self.waddstr (TITLE_VERTIC_LENGTH, 0, space)
        return

    def print_requesttarget (self, target, number) :

        if target.state :
            line_color = curses.color_pair (DEFAULT_COLOR)
        else :
            line_color = curses.A_BOLD

        linenum = number + TITLE_VERTIC_LENGTH

        # Print values
        values_str = " %3d%% %4d  " % (int(target.lossrate),target.snt)

        # Print ping line
        self.waddstr (linenum, self.start_hostname,
                            target.name[0:self.length_hostname], line_color)
        self.waddstr (linenum, self.start_url,
                            target.url[0:self.length_url] + ":" + target.port, line_color)
        # TODO: ↑多分直さないとだめ。現状はtarget.urlの後ろに直接結合してる。

        self.waddstr (linenum, self.ref_start, values_str, line_color)

        for n in range (len (target.result)) :
            if target.result[n] != "X" and target.result[n] != "t":
                color = curses.color_pair (UP_COLOR)
            else :
                color = curses.color_pair (DOWN_COLOR)

            y, x = self.stdscr.getmaxyx()
            if self.res_start + n > x :
                continue
            self.waddstr (linenum, self.res_start + n,
                                target.result[n], color)

        y, x = self.stdscr.getmaxyx()
        self.waddstr (linenum, x - len (REAR), REAR)

    def print_arrow (self, number) :
        linenum = number + TITLE_VERTIC_LENGTH

        self.waddstr (linenum, self.start_arrow, ARROW)
        self.stdscr.move (0, 0)
        self.stdscr.refresh ()
        return

    def erase_arrow (self, number) :
        linenum = number + TITLE_VERTIC_LENGTH

        space_str = ""
        for x in range (len (ARROW)) :
            space_str += " "

        self.waddstr (linenum, self.start_arrow, space_str)
        self.stdscr.move (0, 0)
        self.stdscr.refresh ()
        return

    def erase_requesttarget (self, number) :
        linenum = number + TITLE_VERTIC_LENGTH
        space = ""
        for x in range (self.x) :
            space += " "
        self.waddstr (linenum, 2, space)
        return

class Portman :

    def __init__ (self, stdscr, configfile) :

        self.curs = CursesCtrl (stdscr)
        self.configfile = configfile
        self.targets = []

        self.addtargets ()

        signal.signal(signal.SIGHUP, self.updatetargets)
        signal.siginterrupt(signal.SIGHUP, False)

        self.curs.print_title()

        return

    def addtargets (self) :
        newtargets = []
        self.targetlist = self.gettargetlist (self.configfile)

        for name, url, port in self.targetlist :

            pt = RequestTarget (name, url, port)
            idx = -1
            if pt in self.targets :
                idx = self.targets.index (pt)
                newtargets.append (self.targets[idx])
            else:
                newtargets.append (pt)

        self.targets = newtargets
        self.curs.update_info (self.targets)

    def main (self) :

        thread.start_new_thread(self.curs.key_thread, tuple(self.targets))

        # print blank line
        num = 0
        for target in self.targets :
            num += 1
            self.curs.print_requesttarget (target, num)

        while True :

            self.curs.update_info (self.targets)
            self.curs.erase_title ()
            self.curs.print_title ()
            self.curs.erase_reference ()
            self.curs.print_reference ()

            num = 0
            for target in self.targets :
                num += 1

                self.curs.print_arrow (num)
                target.send ()
                self.curs.erase_requesttarget (num)
                self.curs.print_requesttarget (target, num)
                time.sleep (REQ_INTERVAL)
                self.curs.erase_arrow (num)

            self.curs.print_arrow (num)
            time.sleep (REQ_ALLTARGET_INTERVAL)
            self.curs.erase_arrow (num)
            self.curs.erase_requesttarget (num + 1)

    def updatetargets (self, signum, frame) :
        self.addtargets ()
        self.curs.refresh ()

    def gettargetlist (self, configfile) :

        try :
            cf = open (configfile, "r")
        except :
            sys.exit (r'can not open config file "%s"' % (configfile))

        targetlist = []

        for line in cf :

            line = re.sub ('\t', ' ', line)
            line = re.sub ('\s+', ' ', line)
            line = re.sub ('^#.*', '', line)
            line = re.sub (';\s*#', '', line)
            line = line.strip (' \r\n')
            line = line.rstrip (' \r\n')

            if line == "" :
                continue

            ss = line.split (' ')
            name = ss.pop (0)
            url = ss.pop (0)
            port = ss.pop(0)
            # source = None
            # relay = {}
            # for s in ss :
            #     key, value = s.split ("=")
            #     if key in ("os", "relay", "via", "community", "netns", "user", "key") :
            #         relay[key] = value
            #     elif key == "source" :
            #         source = value

            targetlist.append ([name, url, port])

        cf.close ()

        return targetlist

def main (stdscr) :

    curses.start_color ()
    curses.use_default_colors ()
    curses.init_pair (DEFAULT_COLOR, -1, -1)
    curses.init_pair (UP_COLOR, curses.COLOR_GREEN, -1)
    curses.init_pair (DOWN_COLOR, curses.COLOR_RED, -1)

    """
    XXX: parse and validating config file shoud be done before curses.wrapper.
    """

    httpneet = Portman (stdscr, CONFIGFILE)
    httpneet.main ()

    return


if __name__ == '__main__' :

    desc = "usage : %prog [options] configfile"
    parser = OptionParser (desc)

    (options, args) = parser.parse_args ()

    try :
        CONFIGFILE = args.pop ()
    except :
        sys.stderr.write ("config file is not specified. portman configfile\n")
        sys.exit ()

    try :
        curses.wrapper (main)

    except KeyboardInterrupt :
        sys.exit(0)