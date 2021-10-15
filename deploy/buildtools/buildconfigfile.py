""" This converts the build configuration files into something usable by the
manager """

from time import strftime, gmtime
import ConfigParser
import pprint
import logging

from runtools.runtime_config import RuntimeHWDB
from awstools.awstools import auto_create_bucket, get_snsname_arn
from buildtools.buildconfig import BuildConfig

rootLogger = logging.getLogger()

class BuildConfigFile:
    """ Configuration class for builds. This is the "global" configfile, i.e.
    sample_config_build.ini """

    def __init__(self, args):
        if args.launchtime:
            launch_time = args.launchtime
        else:
            launch_time = strftime("%Y-%m-%d--%H-%M-%S", gmtime())

        self.args = args

        global_build_configfile = ConfigParser.ConfigParser(allow_no_value=True)
        # make option names case sensitive
        global_build_configfile.optionxform = str
        global_build_configfile.read(args.buildconfigfile)

        # aws specific options
        self.agfistoshare = [x[0] for x in global_build_configfile.items('agfistoshare')]
        self.acctids_to_sharewith = [x[1] for x in global_build_configfile.items('sharewithaccounts')]

        # this is a list of actual builds to run
        builds_to_run_list = map(lambda x: x[0], global_build_configfile.items('builds'))

        build_recipes_configfile = ConfigParser.ConfigParser(allow_no_value=True)
        # make option names case sensitive
        build_recipes_configfile.optionxform = str
        build_recipes_configfile.read(args.buildrecipesconfigfile)

        build_hosts_configfile = ConfigParser.ConfigParser(allow_no_value=True)
        # make option names case sensitive
        build_hosts_configfile.optionxform = str
        build_hosts_configfile.read(args.buildhostsconfigfile)

        build_recipes = dict()
        for section in build_recipes_configfile.sections():
            build_recipes[section] = BuildConfig(
                section,
                dict(build_recipes_configfile.items(section)),
                build_hosts_configfile,
                self,
                launch_time)

        self.hwdb = RuntimeHWDB(args.hwdbconfigfile)

        self.builds_list = list(map(lambda x: build_recipes[x], builds_to_run_list))

    def setup(self):
        """ Setup based on the types of buildhosts """
        for build in self.builds_list:
            auto_create_bucket(build.s3_bucketname)
            #check to see email notifications can be subscribed
            get_snsname_arn()

    def launch_build_instances(self):
        """ Launch an instance for the builds we want to do """
        # TODO: optimization: batch together items using the same buildhost
        for build in self.builds_list:
            build.build_farm_dispatcher.launch_build_instance()

    def wait_build_instances(self):
        """ block until all build instances are launched """
        for build in self.builds_list:
            build.build_farm_dispatcher.wait_on_instance_launch()

    def terminate_all_build_instances(self):
        for build in self.builds_list:
            build.build_farm_dispatcher.terminate_build_instance()

    def get_build_by_ip(self, nodeip):
        """ For a particular private IP (aka instance), return the BuildConfig
        that it's supposed to be running. """
        for build in self.builds_list:
            if build.build_farm_dispatcher.get_build_instance_private_ip() == nodeip:
                return build
        return None

    def get_build_instance_ips(self):
        """ Return a list of all the build instance IPs, i.e. hosts to pass to
        fabric. """
        return map(lambda x: x.build_farm_dispatcher.get_build_instance_private_ip(), self.builds_list)

    def get_builds_list(self):
        return self.builds_list

    def __str__(self):
        return pprint.pformat(vars(self))

