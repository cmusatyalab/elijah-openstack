#!/usr/bin/env python

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import SocketServer
import time
from urlparse import urlparse, parse_qs

import heatlib

vm_info = {}
heat = heatlib.start_heat_connection()

class CloudletHandler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        global vm_info

        self._set_headers()

        #print "GET message: ", urlparse(self.path).query
	query_paras = parse_qs(urlparse(self.path).query)

        user_id = query_paras.get("user_id")[0]
        app_id = query_paras.get("app_id")[0]
        print user_id, app_id

        try:
            user_app_vm_info = vm_info[user_id][app_id]
            stack_id = user_app_vm_info['stack_id']
            public_ip = heatlib.get_stack_ip(heat, stack_id)
            if public_ip is not None:
                user_app_vm_info['public_ip'] = public_ip
                self.wfile.write(public_ip)
            else:
                self.wfile.write("None")
        except KeyError:
            print "Stack ID missing. VM management is not working properly!"
            self.wfile.write("Error")

    def do_POST(self):
        global vm_info

        self._set_headers()

        post_msg = self.rfile.read(int(self.headers['Content-Length']))
        #print "POST message: ", post_msg
        query_paras = parse_qs(post_msg)

        user_id = query_paras.get("user_id")[0]
        app_id = query_paras.get("app_id")[0]
        action = query_paras.get("action")[0]
        print user_id, app_id, action

        if action == "create":
            stack_id = heatlib.create_stack(heat, template_file = "templates/%s-template.yaml" % app_id, stack_name = user_id, instance_name = app_id)
            
            if vm_info.get(user_id, None) is None:
                vm_info[user_id] = {}
            vm_info[user_id][app_id] = {'stack_id': stack_id}
        elif action == "delete":
            try:
                stack_id = vm_info[user_id][app_id]['stack_id']
                heatlib.delete_stack(heat, stack_id)
                del vm_info[user_id][app_id]
            except KeyError:
                pass

        self.wfile.write("Success")

class ThreadingHTTPServer(SocketServer.ThreadingMixIn, HTTPServer):
    def finish_request(self, request, client_address):
        request.settimeout(10)
        # "super" can not be used because BaseServer is not created from object
        HTTPServer.finish_request(self, request, client_address)


def run(server_class = ThreadingHTTPServer, handler_class = CloudletHandler, port = 9127):
    server_address = ('8.225.186.10', port)
    httpd = server_class(server_address, handler_class)
    print "Server has initialized"
    httpd.serve_forever()

if __name__ == "__main__":
    from sys import argv

    if len(argv) == 2:
        run(port = int(argv[1]))
    else:
        run()
