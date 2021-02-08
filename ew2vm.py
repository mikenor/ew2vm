# ew2vm.py Copyright (c) 2021 Michael Norton
# https://github.com/mikenor/ew2vm
# 
# MIT License
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import argparse
try:
    import colorama
    colorama.init()
except:
    pass
import collections
import dns.resolver
import json
import re
import socket
import struct
import threading
import time
import urllib.parse






content_sent = ''
contentvisible = True
contentvisible_pending = False
credit = ''
credit_sent = ''
ew_connected = False
ew_txqueue = collections.deque()
imagehash = ''
imagehash_pending = ''
liverev = 0
liverev_pending = -1
pres_rowid = 0
presentation_filter_re = None
presentation_filtered = True
requestrev = 0
slide_rowid_pending = -1
slides = {}
title = ''
vm_connected = False
vm_txqueue = collections.deque()






def main():
    global args, credit_slide_re, ew_connected, presentation_filter_re, vm_connected
    ew_rxthread = None
    ew_socket = None
    ew_txthread = None
    vm_rxthread = None
    vm_socket = None
    vm_txthread = None

    # get/process command-line arguments
    arg_parser = argparse.ArgumentParser(usage='%(prog)s --vm-input NUM [options] | --help', description='Sends text from EasyWorship presentation/song slides to a vMix Title input using the TCP APIs of both programs.', epilog='EW2VM Copyright (c) 2021 Michael Norton. MIT License; see LICENSE.md file for details.', allow_abbrev=False)
    arg_parser.add_argument('--ew-host', default='::1', metavar='HOST', help='network address where EasyWorship is running (default ::1)')
    arg_parser.add_argument('--ew-client-id', default='a164e834-fc66-4cff-8e47-aa904ee9e62b', metavar='GUID', help='client ID for connection to EasyWorship (e.g. if running multiple instances of %(prog)s simultaneously)')
    arg_parser.add_argument('--vm-host', default='::1', metavar='HOST', help='network address where vMix is running (default ::1)')
    arg_parser.add_argument('--vm-input', required=True, type=int, metavar='NUM', help='vMix input number')
    arg_parser.add_argument('--vm-textbox', type=int, default=0, metavar='INDEX', help='textbox on vMix Title in which to place main slide text (default 0)')
    arg_parser.add_argument('--vm-textbox-credit', type=int, default=1, metavar='INDEX', help='textbox on vMix Title in which to place title/credit text (default 1)')
    arg_parser.add_argument('--presentation-filter', nargs='+', metavar='TAG', help='only show presentations/songs that contain any slide with any TAG in the slide title')
    arg_parser.add_argument('--credit-slide', nargs='+', default=['Title', 'Credit', 'Credits'], metavar='TAG', help='use the text from slide with any TAG in its title as custom title/credit text for the whole presentation/song (default "Title" "Credit" "Credits")')
    args = arg_parser.parse_args()
    
    if args.presentation_filter:
        presentation_filter_re = re.compile('(?:\A|\s)(' + '|'.join(args.presentation_filter) + ')(?:\s|\Z)', re.IGNORECASE)
    
    if args.credit_slide:
        credit_slide_re = re.compile('(?:\A|\s)(' + '|'.join(args.credit_slide) + ')(?:\s|\Z)', re.IGNORECASE)
    else:
        credit_slide_re = re.compile('\Z.')

    print('\33[91mEW2VM STARTING (CTRL+C TO TERMINATE)...\033[0m')
    
    # resolve IP of ew with getaddrinfo so we can query the IP for mdns records with dns.resolver
    ew_resolver = dns.resolver.Resolver(configure=False)
    ew_resolver.nameservers = [addrinfo[4][0] for addrinfo in socket.getaddrinfo(args.ew_host, 5353, proto=socket.IPPROTO_UDP)]
    ew_resolver.port = 5353
    ew_resolver.timeout = 3
    
    try:
        # main loop, infinitely attempt connections to ew and vm
        while True:
            
            # connect to vm
            if not vm_connected:
                print('\33[91mNot connected to VM.\033[0m')
                
                # clean up any existing connection
                disconnect(vm_socket, vm_txthread, vm_rxthread, 'VM')
                              
                try:
                    # open new socket
                    print('\33[91mConnecting to VM at ' + args.vm_host + ' port 8099...\033[0m')
                    vm_socket = socket.create_connection((args.vm_host, 8099), 7)
                except OSError:
                    vm_socket = None
                    print('\33[91mConnecting to VM failed!\033[0m')
                else:
                    print('\33[91mConnected to VM.\033[0m')
                    vm_connected = True
                    
                    # flush tx message queue
                    vm_txqueue.clear()
                    
                    # start communication threads
                    vm_txthread = threading.Thread(target=send_vm, name='vm_txthread', args=([vm_socket]))
                    vm_txthread.start()
                    vm_rxthread = threading.Thread(target=recv_vm, name='vm_rxthread', args=([vm_socket]))
                    vm_rxthread.start()

            # connect to ew
            if not ew_connected:
                print('\33[91mNot connected to EW.\033[0m')
                
                # clean up any existing connection
                disconnect(ew_socket, ew_txthread, ew_rxthread, 'EW')
                
                try:
                    # resolve mdns records to determine dynamic EW port (new in EW 7.2.3)
                    print('\33[91mSearching for EW on ' + str(ew_resolver.nameservers) + '...\033[0m')
                    ew_resolution = ew_resolver.resolve('_ezwremote._tcp.local.', rdtype=dns.rdatatype.PTR)
                    ew_srv_name = ew_resolution.rrset[0].target
                    ew_port = ew_resolution.response.find_rrset(dns.message.ADDITIONAL, ew_srv_name, dns.rdataclass.IN, dns.rdatatype.SRV)[0].port
                
                    # open new socket
                    print('\33[91mConnecting to EW at ' + args.ew_host + ' port ' + str(ew_port) + '...\033[0m')
                    ew_socket = socket.create_connection((args.ew_host, ew_port), 7)
                except (OSError, dns.exception.Timeout, dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                    ew_socket = None
                    print('\33[91mConnecting to EW failed!\033[0m')
                else:
                    print('\33[91mConnected to EW.\033[0m')
                    ew_connected = True
                    
                    # flush tx message queue
                    ew_txqueue.clear()
                    
                    # start communication threads
                    ew_txthread = threading.Thread(target=send_ew, name='ew_txthread', args=([ew_socket]))
                    ew_txthread.start()
                    ew_rxthread = threading.Thread(target=recv_ew, name='ew_rxthread', args=([ew_socket]))
                    ew_rxthread.start()

                    # hello to ew
                    ew_txqueue.append(('{"device_type":0,"action":"connect","uid":"' + args.ew_client_id + '","device_name":"ew2vm (Input ' + str(args.vm_input) + ' @ ' + args.vm_host + ')"}\r\n').encode('utf-8'))

            # main loop is loop
            time.sleep(2)
            
    except KeyboardInterrupt:
        print('\33[91mEW2VM TERMINATING...\033[0m')
        
    finally:
        vm_connected = False
        disconnect(vm_socket, vm_txthread, vm_rxthread, 'VM')
        ew_connected = False
        disconnect(ew_socket, ew_txthread, ew_rxthread, 'EW')

    print('\33[91mEW2VM FINISHED.\033[0m')






# close and cleanup TCP connection with ew/vm
def disconnect(thesocket=None, txthread=None, rxthread=None, description='something'):    
    if thesocket:
        # close existing socket if applicable
        print('\33[91mClosing connection to ' + description + '...\033[0m')
        try:
            thesocket.settimeout(0)
        except OSError:
            pass
        try:
            thesocket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            thesocket.settimeout(None)
        except OSError:
            pass
        try:
            thesocket.close()
        except OSError:
            pass
    
    # wait for communication threads to die if applicable
    if txthread:
        if txthread.is_alive():
            print('\33[91mWaiting for ' + description + ' transmit to finish...\033[0m')
            txthread.join()
    if rxthread:
        if rxthread.is_alive():
            print('\33[91mWaiting for ' + description + ' receive to finish...\033[0m')
            rxthread.join()






# process received ew message
def procmsg_ew(jsondata, rawdata):
    global content_sent, contentvisible, contentvisible_pending, credit, credit_sent, imagehash, imagehash_pending, liverev, liverev_pending, pres_rowid, presentation_filtered, requestrev, slide_rowid_pending, slides, title
    
    if 'requestrev' in jsondata:
        requestrev = int(jsondata['requestrev'])

    if 'action' in jsondata:
                    
        if jsondata['action'] == 'status':                
            if 'liverev' in jsondata:
                liverev_pending = int(jsondata['liverev'])
            if 'imagehash' in jsondata:
                imagehash_pending = jsondata['imagehash']
                slide_rowid_pending = int(jsondata.get('slide_rowid', -1))
            if True in [bool(jsondata.get('logo', False)), bool(jsondata.get('black', False)), bool(jsondata.get('clear', False))]:
                contentvisible_pending = False
            else:
                contentvisible_pending = True


        elif jsondata['action'] == 'LiveData':
            
            # clear stored slides
            credit = ''
            presentation_filtered = True
            slides = {}
            title = ''
            
            # unpack first part of raw data
            unknownrawdata0, liverev, pres_rowid, title_revision, pres_len, unknownrawdata5 = struct.unpack('<lqqqlq', rawdata[:40])
            #print((unknownrawdata0, liverev, pres_rowid, title_revision, pres_len, unknownrawdata5))
                        
            # request title info
            ew_txqueue.append(('{"slide_rowid":0,"revision":' + str(title_revision) + ',"action":"getSlideInfo","requestrev":' + str(requestrev) + ',"rectype":1,"pres_rowid":' + str(pres_rowid) + '}\r\n').encode('utf-8'))
            
            # store preliminary info of each slide
            for i in range(pres_len):
                slide = {}
                slide['id'] = i
                slide['slide_rowid'], slide['revision'] = struct.unpack('<qq', rawdata[(40 + (16 * i)):(56 + (16 * i))])
                slide['infoReceived'] = False
                slide['infoRequested'] = False
                slides[slide['slide_rowid']] = slide
                                              

        elif jsondata['action'] == 'slideInfo' and 'slide_rowid' in jsondata:
            
            if int(jsondata['slide_rowid']) == 0: # slide 0 info is for the song title (not for an actual slide)
                if 'title' in jsondata:
                    title = jsondata['title']
                    
            if int(jsondata['slide_rowid']) in slides: # info is for a valid slide
                
                if credit_slide_re.search(jsondata.get('title', '')): # slide is a special slide of custom song credits
                    credit = jsondata.get('content', '')
                    # store blank lyrics for this slide
                    slides[int(jsondata['slide_rowid'])]['content'] = ''
                    
                else: # info is for regular slide
                    if 'content' in jsondata:
                        slides[int(jsondata['slide_rowid'])]['content'] = jsondata['content']
                    if 'title' in jsondata:
                        slides[int(jsondata['slide_rowid'])]['title'] = jsondata['title']
                        
                slides[int(jsondata['slide_rowid'])]['infoReceived'] = True
                
                if not presentation_filter_re: # presentation filtering is not enabled
                    presentation_filtered = False
                else:
                    if presentation_filter_re.search(jsondata.get('title', '')): # slide title matches filter
                        presentation_filtered = False
    
    
    if contentvisible_pending: # content should be visible
        
        if imagehash_pending != imagehash: # outdated content is currently output
            
            if liverev_pending != liverev: # outdated slides are currently loaded
                # invalidate queued outbound requests
                ew_txqueue.clear()
                # clear stored slides
                credit = ''
                presentation_filtered = True
                slides = {}
                title = ''
                # request data about new song
                ew_txqueue.append(('{"action":"GetLiveData","requestrev":' + str(requestrev) + '}\r\n').encode('utf-8'))
            
            else:
                # make sure all slides are loaded
                waiting_for_slideinfo = False
                for slide_rowid in slides:
                    if not slides[slide_rowid].get('infoRequested', False):
                        # request more info of slide
                        ew_txqueue.append(('{"slide_rowid":' + str(slide_rowid) + ',"revision":' + str(slides[slide_rowid]['revision']) + ',"action":"getSlideInfo","requestrev":' + str(requestrev) + ',"rectype":1,"pres_rowid":' + str(pres_rowid) + '}\r\n').encode('utf-8'))
                        slides[slide_rowid]['infoRequested'] = True
                    if not slides[slide_rowid].get('infoReceived', False):
                        waiting_for_slideinfo = True
                    
                if not waiting_for_slideinfo and slide_rowid_pending in slides:
                    if presentation_filtered:
                        print('\33[91mINFO: Presentation ignored by filter ("' + '" or "'.join(args.presentation_filter) + '").\033[0m')
                        contentvisible_pending = False
                    else:
                        if 'content' in slides[slide_rowid_pending]: # we have the content of the new slide
                            content_new = slides[slide_rowid_pending]['content']
                            # send content to vm
                            if content_sent != content_new:
                                vm_txqueue.append(('FUNCTION SetText Input=' + str(args.vm_input) + '&SelectedIndex=' + str(args.vm_textbox) + '&Value=' + urllib.parse.quote(content_new) + '\r\n').encode('utf-8'))
                                content_sent = content_new
                            # check if we have custom credit text to send, otherwise use song title
                            if credit != '':
                                credit_new = credit
                            else:
                                print('\33[91mINFO: No custom credit slide ("' + '" or "'.join(args.credit_slide) + '") loaded, resorting to title.\033[0m')
                                credit_new = title
                            # send credit/title to vm
                            if credit_sent != credit_new:
                                vm_txqueue.append(('FUNCTION SetText Input=' + str(args.vm_input) + '&SelectedIndex=' + str(args.vm_textbox_credit) + '&Value=' + urllib.parse.quote(credit_new) + '\r\n').encode('utf-8'))
                                credit_sent = credit_new

                            imagehash = imagehash_pending
                            
        if imagehash_pending == imagehash: # correct content is currently output
            if not contentvisible: # content should be visible but is currently hidden
                # send unhide commands to vm
                vm_txqueue.append(('FUNCTION SetTextVisibleOn Input=' + str(args.vm_input) + '&SelectedIndex=' + str(args.vm_textbox) + '\r\n').encode('utf-8'))
                vm_txqueue.append(('FUNCTION SetTextVisibleOn Input=' + str(args.vm_input) + '&SelectedIndex=' + str(args.vm_textbox_credit) + '\r\n').encode('utf-8'))
                contentvisible = True
                
    if (not contentvisible_pending) and contentvisible: # content should be hidden but is currently visible
        # send hide commands to vm
        vm_txqueue.append(('FUNCTION SetTextVisibleOff Input=' + str(args.vm_input) + '&SelectedIndex=' + str(args.vm_textbox) + '\r\n').encode('utf-8'))
        vm_txqueue.append(('FUNCTION SetTextVisibleOff Input=' + str(args.vm_input) + '&SelectedIndex=' + str(args.vm_textbox_credit) + '\r\n').encode('utf-8'))
        contentvisible = False






# process received vm message
def procmsg_vm(message):
    pass # meh






# receive ew communications
def recv_ew(ew_socket):
    global ew_connected
    received_data = b''
    extrabytes_len = 0
    newjson = {}
    newjson_len = -1
    
    while ew_connected:
        try:
            ew_socket.settimeout(None)
            # receive data from socket
            received_data += ew_socket.recv(16384)
        except OSError:
            ew_connected = False
        else:
            if len(received_data) < 1:
                ew_connected = False
        finally:
            # find first message delimiter
            newjson_len = received_data.find(b'\r\n')
            while newjson_len != -1:
                
                print('RECV-EW: \33[94m' + received_data[:newjson_len].decode('utf-8').encode('unicode_escape').decode('utf-8') + '\033[0m')
                
                extrabytes_len = 0
                try:
                    newjson = json.loads(received_data[:newjson_len].decode('utf-8'))
                except json.decoder.JSONDecodeError: # message is not valid json
                    newjson = ''
                else:
                    if newjson.get('action', '') in ['LiveData', 'ScheduleData', 'currentImage', 'slideImage']:
                        # json message says it will have extra bytes following
                        extrabytes_len = int(newjson.get('size', 0))
                finally:
                    if len(received_data) >= (newjson_len + 2 + extrabytes_len): # message is complete incl extra bytes
                        if newjson != '':
                            # process received message
                            procmsg_ew(newjson, received_data[(newjson_len + 2):(newjson_len + 2 + extrabytes_len)])
                        # look in received data for another message
                        received_data = received_data[(newjson_len + 2 + extrabytes_len):]
                        newjson_len = received_data.find(b'\r\n')
                    else:
                        # don't have full message with all extra bytes, need to receive more data
                        newjson_len = -1

    
    



# receive vm communications
def recv_vm(vm_socket):
    global vm_connected
    received_data = b''
    newmsg_len = -1
    
    while vm_connected:
        try:
            vm_socket.settimeout(None)
            # receive data from socket
            received_data += vm_socket.recv(2048)
        except OSError:
            vm_connected = False
        else:
            if len(received_data) < 1:
                vm_connected = False
        finally:
            # find first message delimiter
            newmsg_len = received_data.find(b'\r\n')
            while newmsg_len != -1:
                print('RECV-VM: \33[92m' + received_data[:newmsg_len].decode('utf-8').encode('unicode_escape').decode('utf-8') + '\033[0m')
                if newmsg_len > 0:
                    # process received message
                    procmsg_vm(received_data[:newmsg_len])
                # look in received data for another message
                received_data = received_data[(newmsg_len + 2):]
                newmsg_len = received_data.find(b'\r\n')






# send ew communication from outgoing message queue
def send_ew(ew_socket):
    global ew_connected
    sentbytestimestamp = time.time()
    
    while ew_connected:
        outboundbytes = b''
        try:
            while True:
                # retrieve queue until it's emptied
                outboundbytes += ew_txqueue.popleft()
        except IndexError:
            # queue is empty
            if len(outboundbytes) < 1:
                # no messages retrieved from queue
                if (time.time() - sentbytestimestamp) > 3:
                    # more than 3 seconds since last transmission, so transmit keepalive
                    outboundbytes = ('{"action":"heartbeat","requestrev":' + str(requestrev) + '}\r\n').encode('utf-8')
                else:
                    # wait before checking the queue again
                    time.sleep(0.002)
            if len(outboundbytes) > 0:
                sentbytecount_total = 0
                while sentbytecount_total < len(outboundbytes):
                    try:
                        ew_socket.settimeout(7)
                        sentbytecount = ew_socket.send(outboundbytes[sentbytecount_total:])
                        ew_socket.settimeout(None)
                    except OSError:
                        ew_connected = False
                        outboundbytes = b''
                    else:
                        if sentbytecount < 1:
                            ew_connected = False
                            outboundbytes = b''
                        else:
                            sentbytestimestamp = time.time()
                            print('SEND-EW: \33[95m' + outboundbytes[sentbytecount_total:sentbytecount_total + sentbytecount].decode('utf-8').encode('unicode_escape').decode('utf-8') + '\033[0m')
                            sentbytecount_total += sentbytecount






# send vm communication from outgoing message queue
def send_vm(vm_socket):
    global vm_connected
    
    while vm_connected:
        outboundbytes = b''
        try:
            while True:
                # retrieve queue until it's emptied
                outboundbytes += vm_txqueue.popleft()
        except IndexError:
            # queue is empty
            if len(outboundbytes) < 1:
                # no messages retrieved from queue, wait before checking the queue again
                time.sleep(0.002)
            else:
                sentbytecount_total = 0
                while sentbytecount_total < len(outboundbytes):
                    try:
                        vm_socket.settimeout(7)
                        sentbytecount = vm_socket.send(outboundbytes[sentbytecount_total:])
                        vm_socket.settimeout(None)
                    except OSError:
                        vm_connected = False
                        outboundbytes = b''
                    else:
                        if sentbytecount < 1:
                            vm_connected = False
                            outboundbytes = b''
                        else:
                            print('SEND-VM: \33[93m' + outboundbytes[sentbytecount_total:sentbytecount_total + sentbytecount].decode('utf-8').encode('unicode_escape').decode('utf-8') + '\033[0m')
                            sentbytecount_total += sentbytecount






# main
if __name__ == '__main__':
    main()


