#!/usr/bin/python

from __future__ import absolute_import

import datetime
import functools
import json
import logging
import os
import socket
import time
import unittest

import send_signifai

try:
    # Python 3.6
    import http.client as http_client
except ImportError:
    # Python 2.7
    import httplib as http_client

try:
    # Python 3.6
    import unittest.mock as unittest_mock
except ImportError:
    # Python 2.7 with 'mock' module
    import mock as unittest_mock


__author__ = "SignifAI, Inc."
__copyright__ = "Copyright (C) 2018, SignifAI, Inc."
__version__ = "1.0"


class TestHTTPPost(unittest.TestCase):
    corpus = {
        "event_source": "nagios",
        "service": "httpd",
        "timestamp": time.time(),
        "event_description": "web server down",
        "value": "critical",
        "attributes": {"state": "alarm"}
    }
    events = {"events": [corpus]}

    def setUp(self):
        hplog = logging.getLogger("http_post")
        hplog.setLevel(100)
        bslog = logging.getLogger("bugsnag_unattached_notify")
        bslog.setLevel(100)

    # Connection failure handling tests
    #   - Connection initialization
    def test_post_bad_host(self):
        # Should return False, NOT throw
        # (don't use a mock for this, it should never touch the collector)
        result = send_signifai.POST_data(auth_key="", data=self.events,
                                         signifai_host="noresolve.signifai.io")
        self.assertFalse(result)

    def test_create_exception(self):
        with unittest_mock.patch.object(http_client.HTTPSConnection,
                                        '__init__',
                                        side_effect=http_client.HTTPException) as conn_call:  # noqa
            result = send_signifai.POST_data(auth_key="", data=self.events)
        self.assertFalse(result)
        # Ensure we don't attempt a retry
        self.assertEqual(conn_call.call_count, 1)

    def test_connect_exception(self):
        # Should return False

        with unittest_mock.patch.object(http_client.HTTPSConnection,
                                        'connect',
                                        side_effect=http_client.HTTPException) as conn_call:  # noqa
            result = send_signifai.POST_data(auth_key="", data=self.events)

        self.assertFalse(result)
        # Ensure we attempted retries
        self.assertEqual(conn_call.call_count, 5)

    #   - Retry mechanism
    def test_connect_retries_fail(self):
        # Should return False
        total_retries = 5

        with unittest_mock.patch.object(http_client.HTTPSConnection,
                                        'connect',
                                        side_effect=socket.timeout) as conn_call:  # noqa
            result = send_signifai.POST_data(auth_key="", data=self.events,
                                             attempts=total_retries)
        self.assertFalse(result)
        self.assertEqual(conn_call.call_count, total_retries)

    def test_connect_retries_can_succeed(self):
        # Should return True
        total_retries = 5

        def conn_mock():
            if m['connect'].call_count < (total_retries - 1):
                raise socket.timeout
            else:
                return True

        def getresponse_mock():
            ret = unittest_mock.Mock()
            ret.status = 200
            ret.read.return_value = json.dumps({
                "success": True,
                "failed_events": []
            })
            return ret

        with unittest_mock.patch.multiple(http_client.HTTPSConnection,
                                          connect=unittest_mock.DEFAULT,
                                          getresponse=unittest_mock.DEFAULT,
                                          request=unittest_mock.DEFAULT) as m:
            m['connect'].side_effect = conn_mock
            m['getresponse'].side_effect = getresponse_mock
            result = send_signifai.POST_data(auth_key="", data=self.events,
                                             attempts=total_retries)

        self.assertTrue(result)
        self.assertEqual(m['connect'].call_count, total_retries - 1)

    # Transport failures (requesting, getting response)
    #   - Request timeout
    def test_request_timeout(self):
        # Should return False, NOT throw
        with unittest_mock.patch.multiple(http_client.HTTPSConnection,
                                          connect=unittest_mock.DEFAULT,
                                          getresponse=unittest_mock.DEFAULT,
                                          request=unittest_mock.DEFAULT) as m:
            m['request'].side_effect = socket.timeout
            result = send_signifai.POST_data(auth_key="", data=self.events)
        self.assertFalse(result)
        self.assertEqual(m['request'].call_count, 1)

    #   - Misc. request error
    def test_request_httpexception(self):
        # Should return False, NOT throw

        with unittest_mock.patch.multiple(http_client.HTTPSConnection,
                                          connect=unittest_mock.DEFAULT,
                                          getresponse=unittest_mock.DEFAULT,
                                          request=unittest_mock.DEFAULT) as m:
            m['request'].side_effect = http_client.HTTPException
            result = send_signifai.POST_data(auth_key="", data=self.events)
        self.assertFalse(result)

    #   - Getresponse timeout
    def test_getresponse_timeout(self):
        # Should return False, NOT throw

        with unittest_mock.patch.multiple(http_client.HTTPSConnection,
                                          connect=unittest_mock.DEFAULT,
                                          getresponse=unittest_mock.DEFAULT,
                                          request=unittest_mock.DEFAULT) as m:
            m['getresponse'].side_effect = socket.timeout
            result = send_signifai.POST_data(auth_key="", data=self.events)
        self.assertFalse(result)

    #   - Misc. getresponse failure
    def test_getresponse_httpexception(self):
        # Should return False, NOT throw
        with unittest_mock.patch.multiple(http_client.HTTPSConnection,
                                          connect=unittest_mock.DEFAULT,
                                          getresponse=unittest_mock.DEFAULT,
                                          request=unittest_mock.DEFAULT) as m:
            m['getresponse'].side_effect = http_client.HTTPException
            result = send_signifai.POST_data(auth_key="", data=self.events)
        self.assertFalse(result)

    #   - Server error
    def test_post_bad_status(self):
        # Should return False, NOT throw

        with unittest_mock.patch.multiple(http_client.HTTPSConnection,
                                          connect=unittest_mock.DEFAULT,
                                          getresponse=unittest_mock.DEFAULT,
                                          request=unittest_mock.DEFAULT) as m:
            resp = unittest_mock.Mock()
            resp.read.return_value = "500 Internal Server Error"
            resp.status = 500
            m['getresponse'].return_value = resp
            result = send_signifai.POST_data(auth_key="", data=self.events)
        self.assertFalse(result)

    #   - Server sent back non-JSON
    def test_post_bad_response(self):
        # Should return False, NOT throw

        with unittest_mock.patch.multiple(http_client.HTTPSConnection,
                                          connect=unittest_mock.DEFAULT,
                                          getresponse=unittest_mock.DEFAULT,
                                          request=unittest_mock.DEFAULT) as m:
            resp = unittest_mock.Mock()
            resp.read.return_value = "this is a bad response text"
            resp.status = 200
            m['getresponse'].return_value = resp
            result = send_signifai.POST_data(auth_key="", data=self.events)
        self.assertFalse(result)

    # Data correctness failures (all other operations being successful,
    # but the server returned an error/failed event)
    #   - All events fail
    def test_post_bad_corpus(self):
        # Should return False, NOT throw
        def everything_failed_mock(*args, **kwargs):
            body = kwargs['body']
            mockresponse = unittest_mock.Mock()
            mockresponse.read.return_value = json.dumps({
                "success": False,
                "failed_events": json.loads(body)['events']
            })
            mockresponse.status = 200
            m['getresponse'].return_value = mockresponse
            return True

        with unittest_mock.patch.multiple(http_client.HTTPSConnection,
                                          connect=unittest_mock.DEFAULT,
                                          getresponse=unittest_mock.DEFAULT,
                                          request=unittest_mock.DEFAULT) as m:
            m['request'].side_effect = everything_failed_mock
            result = send_signifai.POST_data(auth_key="", data=self.events)
        self.assertIsNone(result)

    #   - Only some events fail (we treat that as a whole failure)
    def test_post_somebad_somegood(self):
        # Should return False, NOT throw
        events = {"events": [self.corpus, self.corpus]}

        def random_event_failure(*args, **kwargs):
            body = kwargs['body']
            mockresponse = unittest_mock.Mock()
            mockresponse.status = 200
            mockresponse.read.return_value = json.dumps({
                "success": True,
                "failed_events": [
                    {
                        "event": json.loads(body)['events'][1],
                        "error": "some error, doesn't matter"
                    }
                ]
            })
            m['getresponse'].return_value = mockresponse

        with unittest_mock.patch.multiple(http_client.HTTPSConnection,
                                          connect=unittest_mock.DEFAULT,
                                          getresponse=unittest_mock.DEFAULT,
                                          request=unittest_mock.DEFAULT) as m:
            m['request'].side_effect = random_event_failure
            result = send_signifai.POST_data(auth_key="", data=events)
        self.assertIsNone(result)

    #   - Ensure request is made as expected based on parameters
    def test_post_request_generation(self):
        # Should return True AND no test case in TestEventGeneration
        # may fail
        test_case = self
        API_KEY = "TEST_API_KEY"

        def request_gen_test(method, uri, body, headers):
            test_case.assertEqual(uri, send_signifai.DEFAULT_POST_URI)
            test_case.assertEqual(body, json.dumps(test_case.events))
            test_case.assertEqual(headers['Authorization'],
                                  "Bearer {KEY}".format(KEY=API_KEY))
            test_case.assertEqual(headers['Content-Type'],
                                  "application/json")
            test_case.assertEqual(headers['Accept'],
                                  "application/json")
            test_case.assertEqual(method, "POST")

        with unittest_mock.patch.multiple(http_client.HTTPSConnection,
                                          connect=unittest_mock.DEFAULT,
                                          getresponse=unittest_mock.DEFAULT,
                                          request=unittest_mock.DEFAULT) as m:
            m['request'].side_effect = request_gen_test
            mockresp = unittest_mock.Mock()
            mockresp.status = 200
            mockresp.read.return_value = json.dumps({
                "success": True,
                "failed_events": []
            })
            m['getresponse'].return_value = mockresp
            result = send_signifai.POST_data(auth_key=API_KEY,
                                             data=self.events)
        self.assertTrue(result)

    # Success tests
    #   - All is well
    def test_good_post(self):
        # Should return True
        with unittest_mock.patch.multiple(http_client.HTTPSConnection,
                                          connect=unittest_mock.DEFAULT,
                                          getresponse=unittest_mock.DEFAULT,
                                          request=unittest_mock.DEFAULT) as m:
            mockresp = unittest_mock.Mock()
            mockresp.status = 200
            mockresp.read.return_value = json.dumps({
                "success": True,
                "failed_events": []
            })
            m['getresponse'].return_value = mockresp
            result = send_signifai.POST_data(auth_key="", data=self.events)
        self.assertTrue(result)


class TestParseZabbixMsg(unittest.TestCase):
    def test_no_colons_anywhere_ever(self):
        with self.assertRaises(ValueError):
            send_signifai.parse_zabbix_msg("this template is not valid")

    def test_colon_only_after_brokenness(self):
        with self.assertRaises(ValueError):
            send_signifai.parse_zabbix_msg(
                "this template has some valid bits but is not valid\n"
                "someData: true")

    def test_success_parse(self):
        h = "data1: value1\ndata2: value2"
        j = send_signifai.parse_zabbix_msg(h)
        self.assertEqual(j, {"data1": "value1", "data2": "value2"})

    def test_success_parse_multiline_value(self):
        h = "data1: value1\ndata2: value2\nvalue2 part 2"
        j = send_signifai.parse_zabbix_msg(h)
        self.assertEqual(j, {
            "data1": "value1",
            "data2": "value2\nvalue2 part 2"
        })

    def test_multiline_with_colon_is_two_different_keys(self):
        """
        If you have a piece of data like:

        ```
        data1: value1
        data2: value2
        but then this part of value2: has a colon
        ```

        Then you'll have _three_ keys: `data1`, `data2`, and
        `But then this part of value2`.

        This is a known limitation and we're just making sure
        it's here.
        """

        h = str.join("\n", ["data1: value1",
                            "data2: value2",
                            "But then this part of value2: has a colon"])
        j = send_signifai.parse_zabbix_msg(h)
        self.assertEqual(j, {
            "data1": "value1",
            "data2": "value2",
            "But then this part of value2": "has a colon"
        })


class TestPrepareRESTEvent(unittest.TestCase):
    BEST_CASE = {
        "EVENT.DATE": "2018-01-14",
        "EVENT.TIME": "02:31:00",
        "TRIGGER.DESCRIPTION": "Something went wrong!",
        "TRIGGER.ID": "1515",
        "TRIGGER.NSEVERITY": "5",
        "TRIGGER.NAME": "boopHost",
        "NODE.NAME": "zabbix01",
        "TRIGGER.EXPRESSION": "errors >= 1",
        "HOST.NAME": "testhost01.zabbix.net",
        "TRIGGER.STATUS": "Problem"
    }

    def test_basic_failure(self):
        with self.assertRaises(ValueError):
            j = send_signifai.prepare_REST_event({"EVENT.TIME": "03:23:00"})

    def test_trigger_status_invalid(self):
        event = self.BEST_CASE.copy()
        event['TRIGGER.STATUS'] = "Unknown"
        with self.assertRaises(KeyError):
            j = send_signifai.prepare_REST_event(event)

    def test_trigger_nseverity_invalid(self):
        event = self.BEST_CASE.copy()
        event['TRIGGER.NSEVERITY'] = "-1"
        with self.assertRaises(KeyError):
            j = send_signifai.prepare_REST_event(event)

    def test_time_without_date_returns_current_time(self):
        """
        If you specify EVENT.TIME and no EVENT.DATE,
        the time of the event should be the current time
        """
        event = self.BEST_CASE.copy()
        h = datetime.datetime.now()
        event.pop("EVENT.DATE")

        with unittest_mock.patch('datetime.datetime') as MockDT:
            MockDT.now = unittest_mock.MagicMock(return_value=h)

            j = send_signifai.prepare_REST_event(event)

        self.assertEqual(j['timestamp'], int(time.mktime(h.timetuple())))

    def test_date_without_time(self):
        """
        If you specify EVENT.DATE but no EVENT.TIME,
        we consider it to be That Date at 00:00:00
        """

        event = self.BEST_CASE.copy()
        event.pop("EVENT.TIME")
        h = datetime.datetime(2018, 1, 14)

        j = send_signifai.prepare_REST_event(event)
        self.assertEqual(j['timestamp'], int(time.mktime(h.timetuple())))

    def test_extra_attributes_get_zabbix_prefix(self):
        """
        If you add attributes we don't know about,
        we transform them into zabbix-namespaced attributes

        If the attribute has spaces, those should be converted
        to underscores
        """

        event = self.BEST_CASE.copy()
        event["AWESOME.ATTR"] = "andyisthebest"
        event["AWESOME.ATTR WITH SPACES"] = "beep"

        j = send_signifai.prepare_REST_event(event)
        awesome_attr_1 = j["attributes"]["zabbix/awesome/attr"]
        awesome_attr_2 = j["attributes"]["zabbix/awesome/attr_with_spaces"]
        self.assertEqual(awesome_attr_1, "andyisthebest")
        self.assertEqual(awesome_attr_2, "beep")

    def test_best_case(self):
        j = send_signifai.prepare_REST_event(self.BEST_CASE)

        self.assertEqual(j, {
            "host": "testhost01.zabbix.net",
            "value": "critical",
            "timestamp": 1515925860,
            "event_source": "zabbix",
            "event_description": "Something went wrong!",
            "attributes": {
                "alert/id": "1515",
                "alert/title": "boopHost",
                "alert/monitoring_host": "zabbix01",
                "alert/condition": "errors >= 1",
                "state": "alarm"
            }
        })


if __name__ == "__main__":
    unittest.main()
