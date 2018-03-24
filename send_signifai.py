#!/usr/bin/python

from __future__ import absolute_import

import json
import logging
import os
import socket
import sys
import time
from copy import deepcopy
from datetime import datetime, time as datetime_time

try:
    # We want to be able to report to bugsnag if present,
    # but if it's not we want to handle that gracefully
    import bugsnag
except ImportError:
    bugsnag = None

try:
    # python3
    import http.client as http_client
except ImportError:
    # python2
    import httplib as http_client

__author__ = "SignifAI, Inc."
__copyright__ = "Copyright (C) 2018, SignifAI, Inc."
__version__ = "1.0"

ATTR_MAP = {
    "TRIGGER.DESCRIPTION": "event_description",
    "TRIGGER.ID": "alert/id",
    "TRIGGER.NAME": "alert/title",
    "TRIGGER.NSEVERITY": "value",
    "HOST.NAME": "host",
    "TRIGGER.STATUS": "state",
    "TRIGGER.EXPRESSION": "alert/condition",
    "NODE.NAME": "alert/monitoring_host"
}
BARE_ATTRS = set(["state"])

MORE_MAPS = {
    "TRIGGER.STATUS": {
        "PROBLEM": "alarm",
        "OK": "ok"
    },
    "TRIGGER.NSEVERITY": {
        "0": "low",
        "1": "low",
        "2": "medium",
        "3": "medium",
        "4": "high",
        "5": "critical"
    }
}

DEFAULT_POST_URI = "/v1/incidents"

def bugsnag_notify(exception, metadata, log=None):
    if not log:
        log = logging.getLogger("bugsnag_unattached_notify")

    if not bugsnag:
        log.warning("Can't notify bugsnag: module not installed!")
        return True

    try:
        bugsnag.notify(exception, meta_data=metadata)
    except Exception:
        # just to prevent bugsnag from crashing the script
        log.warning("Failed to notify bugsnag anyway", exc_info=True)


def POST_data(auth_key, data,
              signifai_host="collectors.signifai.io",
              signifai_port=http_client.HTTPS_PORT,
              signifai_uri=DEFAULT_POST_URI,
              timeout=5,
              attempts=5,
              httpsconn=http_client.HTTPSConnection):
    log = logging.getLogger("http_post")
    client = None
    retries = 0
    bmd = {
        "data": data,
        "signifai_host": signifai_host,
        "signifai_port": signifai_port,
        "signifai_uri": signifai_uri,
        "timeout": timeout,
        "retries": retries,
        "attempts": attempts,
        "httpsconn_class": httpsconn.__name__
    }
    while client is None and retries < attempts:
        bmd['retries'] = retries
        try:
            client = httpsconn(host=signifai_host,
                               port=signifai_port,
                               timeout=timeout)
        except http_client.HTTPException as http_exc:
            # uh, if we can't even create the object, we're toast
            log.fatal("Couldn't create HTTP connection object", exc_info=True)
            bugsnag_notify(http_exc, bmd)
            return False

        try:
            client.connect()
        except socket.timeout:
            # try again until we expire
            log.info("Connection timed out; on retry {retries} of {attempts}"
                     .format(retries=retries, attempts=attempts))
            retries += 1
            client.close()
            client = None
            continue
        except (http_client.HTTPException, socket.error) as http_exc:
            log.fatal("Couldn't connect to SignifAi collector", exc_info=True)
            bugsnag_notify(http_exc, bmd)
            return False

    if client is None and retries == attempts:
        # we expired
        log.fatal("Could not connect successfully after {attempts} attempts"
                  .format(attempts=attempts))
        bugsnag_notify(socket.timeout, bmd)
        return False
    else:
        headers = {
            "Authorization": "Bearer {auth_key}".format(auth_key=auth_key),
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        bmd['headers'] = headers
        res = None
        try:
            client.request("POST", signifai_uri, body=json.dumps(data),
                           headers=headers)
        except socket.timeout as exc:
            # ... don't think we should retry the POST
            log.fatal("POST timed out...?")
            bugsnag_notify(exc, bmd)
            return False
        except (http_client.HTTPException, socket.error) as http_exc:
            # nope
            log.fatal("Couldn't POST to SignifAi Collector", exc_info=True)
            bugsnag_notify(http_exc, bmd)
            return False

        try:
            res = client.getresponse()
        except socket.timeout as exc:
            # ... don't think we should retry here
            log.fatal("Response from server timed out...?")
            bugsnag_notify(exc, bmd)
            return False
        except (http_client.HTTPException, socket.error) as http_exc:
            log.fatal("Couldn't get server response")
            bugsnag_notify(http_exc, bmd)
            return False

        if 200 <= res.status < 300:
            response_text = None
            try:
                response_text = res.read()
                bmd['collector_response'] = response_text
                collector_response = json.loads(response_text)
            except ValueError as exc:
                log.fatal("Didn't receive valid JSON response from collector")
                bugsnag_notify(exc, bmd)
                return False
            except IOError as exc:
                log.fatal("Couldn't read response from collector",
                          exc_info=True)
                bugsnag_notify(exc, bmd)
            else:
                if (not collector_response['success'] or
                        collector_response['failed_events']):
                    errs = collector_response['failed_events']
                    log.fatal("Errors submitting events: {errs}"
                              .format(errs=errs))
                    # Treat it like a ValueError for bugsnag
                    bmd['failed_events'] = collector_response['failed_events']
                    bugsnag_notify(ValueError("errors submitting events"), bmd)
                    # not really False but not really True
                    return None
                else:
                    return True
        else:
            log.fatal("Received error from SignifAi Collector, body follows: ")
            response_text = res.read()
            bmd['collector_response'] = response_text
            log.fatal(response_text)

            bugsnag_notify(ValueError("Error from SignifAi collector"), bmd)
            return False


def parse_zabbix_msg(data):
    lines = data.split("\n")
    last_key = None
    ret = {}

    for line in lines:
        try:
            k, v = line.split(":", 1)
        except ValueError:
            if not last_key:
                raise ValueError("Invalid template")
            ret[last_key] += "\n" + line.strip()
        else:
            last_key = k
            ret[k] = v.strip()

    return ret


def zabbix_key_to_signifai_key(k):
    return k.lower().replace(".", "/").replace(" ", "_").replace("(", "").replace(")", "")


def prepare_REST_event(parsed_data):
    event = {"attributes": {}}
    provided = set(ATTR_MAP.keys())
    event_date = None
    event_time = None
    for k, v in parsed_data.items():
        if k in ATTR_MAP:
            provided.remove(k)
            dst_key = ATTR_MAP[k]
            if k in MORE_MAPS:
                v = MORE_MAPS[k][v.upper()]

            if "/" in dst_key or dst_key in BARE_ATTRS:
                event["attributes"][dst_key] = v
            else:
                event[dst_key] = v
        else:
            if k == "EVENT.DATE":
                try:
                    year, month, day = v.split("-")
                    event_date = datetime(int(year), int(month), int(day))
                except (ValueError, TypeError) as e:
                    pass
            elif k == "EVENT.TIME":
                try:
                    hour, minute, second = v.split(":")
                    event_time = datetime_time(int(hour), int(minute), int(second))
                except (ValueError, TypeError) as e:
                    pass
            else:
                dst_key = "zabbix/{rekey}".format(
                    rekey=zabbix_key_to_signifai_key(k))
                event['attributes'][dst_key] = v

    if event_date:
        if event_time:
            event_date = event_date.replace(
                hour=event_time.hour,
                minute=event_time.minute,
                second=event_time.second
            )
    else:
        event_date = datetime.now()

    if provided:
        raise ValueError("Missing attributes: {attribs}".format(attribs=str.join(", ", provided)))

    event["timestamp"] = int(time.mktime(event_date.timetuple()))
    event["event_source"] = "zabbix"
    return event


def main(argv=sys.argv):
    if len(argv) < 4:
        print("Required args 'to', 'subject' and 'message_body'")
        return 1

    program_name = argv.pop(0)
    api_key = argv.pop(0)
    bugsnag_key = argv.pop(0)
    message_data = argv.pop(0)

    if bugsnag and bugsnag_key:
        project_root = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__)
            )
        )
        bugsnag.configure(
            api_key=bugsnag_key,
            project_root=project_root
        )

    try:
        msg_data = parse_zabbix_msg(message_data)
        REST_event = prepare_REST_event(msg_data)
    except ValueError as val_err:
        print("Error validating/preparing event: {msg}".format(msg=val_err))
        return 1

    l = logging.getLogger("http_post")
    l.addHandler(logging.StreamHandler(sys.stderr))
    l.setLevel(20)
    print(REST_event)

    return POST_data(api_key, REST_event)

if __name__ == "__main__":
    sys.exit(main())