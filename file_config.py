# Licensed Materials - Property of IBM
# Copyright IBM Corp. 2019

import os

def server_url(server):
    return '%s://%s:%s/' % (server.proto, server.ip, server.port)

class FileWriter(object):
    def __init__(self, location, client_cert, signature):
        self._location = location
        self._signature = signature
        if not os.path.exists(self._location):
            os.mkdir(self._location)
        self._client_cert = client_cert
        self._pipe_name = os.path.join(location, 'actions')
        
    def _reload(self):
        print('Monitor', 'RELOAD!')
        with open(self._pipe_name, 'w') as f:
            f.write('reload\n')
        print('Monitor', 'RELOADED!')

    def clean(self):
        # Remove all nginx-streams-job-%s.conf
        if not os.path.exists(self._pipe_name):
            os.mkfifo(self._pipe_name)
  
    def create(self, jobid, config):
        entry = {}
        if config.name == config.applicationName + '_' + jobid:
            location = '/streams/jobs/' + str(jobid) + '/'
        else:
            location = '/' + config.name + '/'

        entry['location'] = location
        entry['servers'] = config.servers
        config.config_file = self._write_file(jobid, [entry])
        self._reload()

    def delete(self, jobid, config):
        if hasattr(config, 'config_file'):
            os.remove(config.config_file)
        self._reload()

    def update(self, jobid, old_config, config):
        # TEMP
        self.delete(jobid, old_config)
        self.create(jobid, config)

    def _write_file(self, jobid, entries):
        cfn = 'nginx-streams-job-%s.conf' % jobid
        tfn = cfn + '.tmp'
        fcfn = os.path.join(self._location, cfn)
        ftfn = os.path.join(self._location, tfn)
        with open(ftfn, 'w') as f:
            for entry in entries:
                self._config_contents(f, jobid, entry)
        os.rename(ftfn, fcfn)
        return fcfn

    def _config_contents(self, f, jobid, entry):
        #f.write('upstream streams_job_%s {\n' % jobid)
        #proto = None
        for server in entry['servers']:
             proto = server.proto
        #    f.write('  server %s;\n' % server_url(server))
        #    f.write('}\n'

        # Work-around dojo not in v5 app images
        f.write('location ^~ %sstreamsx.inet.dojo/ {\n' % entry['location'])
        f.write('  proxy_pass https://ajax.googleapis.com/ajax/libs/dojo/1.14.1/;\n')
        f.write('}\n')

        # If we are checking signatures then two locations are
        # created. The external one that invokes Javascript
        # to verify the signature and then redirect to the internal one.
        # The internal is the full proxy one but is only visible within
        # the server (as it is not protected by any signature authentication).

        # The external location
        f.write('location %s {\n' % entry['location'])
        if self._signature:
            f.write("  set $redirectLocation '/@internal%s';\n" % entry['location'])
            f.write("  js_content checkHTTP;\n")
        else:
            self._proxy_location(f, proto, server)
        f.write('}\n')

        if self._signature:
            f.write('location /@internal%s {\n' % entry['location'])
            f.write('  internal;\n');
            self._proxy_location(f, proto, server)
            f.write('}\n')


    def _proxy_location(self, f, proto, server):

        f.write('  proxy_set_header Host $host;\n')
        f.write('  proxy_set_header X-Real-IP $remote_addr;\n')
        f.write('  proxy_set_header X-Forwarded-Proto %s ;\n' % proto)
        f.write('  proxy_set_header  X-Forwarded-For $remote_addr;\n')
        f.write('  proxy_set_header  X-Forwarded-Host $remote_addr;\n')
        #f.write('  proxy_pass %s://streams_job_%s/;\n' % (proto, jobid))
        f.write('  proxy_pass %s;\n' % (server_url(server)))

        if proto == 'https':
            if self._client_cert:
                f.write('  proxy_ssl_certificate %s;\n' % self._client_cert[0])
                f.write('  proxy_ssl_certificate_key %s;\n' % self._client_cert[1])
