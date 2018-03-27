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
import unittest.mock

import send_signifai

try:
    import http.client as http_client
except ImportError:
    import httplib as http_client

__author__ = "SignifAI, Inc."
__copyright__ = "Copyright (C) 2018, SignifAI, Inc."
__version__ = "1.0"


class BaseHTTPSRespMock(object):
    def __init__(self, data, status=200):
        self.readData = data
        self.status = status

    def read(self, *args, **kwargs):
        # e.g. throw IOError or socket.timeout
        rd = self.readData
        self.readData = ""
        return rd


class BaseHTTPSConnMock(object):
    def __init__(self, *args, **kwargs):
        # e.g. throw HTTPException
        self.args = args
        self.kwargs = kwargs

    def close(self):
        return True

    def connect(self):
        # e.g. try throwing timeout
        return True

    def getresponse(self):
        # e.g. try throwing IOError,
        #      returning bad JSON, etc.
        return BaseHTTPSRespMock("")

    def request(self, *args, **kwargs):
        # e.g. try throwing timeout
        return True


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
        # Should return False
        class AlwaysThrow(BaseHTTPSConnMock):
            retries = 0

            def __init__(self, *args, **kwargs):
                self.__class__.retries += 1
                raise http_client.HTTPException()

        result = send_signifai.POST_data(auth_key="", data=self.events,
                                         httpsconn=AlwaysThrow)
        self.assertFalse(result)
        # Ensure we don't attempt a retry
        self.assertEqual(AlwaysThrow.retries, 1)

    def test_connect_exception(self):
        # Should return False
        class AlwaysThrowOnConnect(BaseHTTPSConnMock):
            retries = 0

            def connect(self, *args, **kwargs):
                self.__class__.retries += 1
                raise http_client.HTTPException()

        result = send_signifai.POST_data(auth_key="", data=self.events,
                                         httpsconn=AlwaysThrowOnConnect)
        self.assertFalse(result)
        # Ensure we attempted retries
        self.assertEqual(AlwaysThrowOnConnect.retries, 5)

    #   - Retry mechanism
    def test_connect_retries_fail(self):
        # Should return False
        total_retries = 5

        class AlwaysTimeout(BaseHTTPSConnMock):
            retry_count = 0

            def __init__(self, *args, **kwargs):
                super(self.__class__, self).__init__(*args, **kwargs)

            def connect(self):
                # The retry mechanism in POST_data will recreate
                # the connection object completely, so we need
                # to store the retries in the class, _not_ the
                # instance
                self.__class__.retry_count += 1
                raise socket.timeout

        result = send_signifai.POST_data(auth_key="", data=self.events,
                                         attempts=total_retries,
                                         httpsconn=AlwaysTimeout)
        self.assertFalse(result)
        self.assertEqual(AlwaysTimeout.retry_count, total_retries)

    def test_connect_retries_can_succeed(self):
        # Should return True
        total_retries = 5

        class SucceedsAtLast(BaseHTTPSConnMock):
            tries = 0

            def connect(self, *args, **kwargs):
                # The retry mechanism in POST_data will recreate
                # the connection object completely, so we need
                # to store the retries in the class, _not_ the
                # instance
                if self.__class__.tries < (total_retries - 1):
                    self.__class__.tries += 1
                    raise socket.timeout
                else:
                    return True

            def getresponse(self):
                return BaseHTTPSRespMock(json.dumps({
                    "success": True,
                    "failed_events": []
                }))

        result = send_signifai.POST_data(auth_key="", data=self.events,
                                         attempts=total_retries,
                                         httpsconn=SucceedsAtLast)
        self.assertTrue(result)

    # Transport failures (requesting, getting response)
    #   - Request timeout
    def test_request_timeout(self):
        # Should return False, NOT throw

        class RequestTimesOut(BaseHTTPSConnMock):
            retries = 0

            def request(self, *args, **kwargs):
                self.__class__.retries += 1
                raise socket.timeout

        result = send_signifai.POST_data(auth_key="", data=self.events,
                                         httpsconn=RequestTimesOut)
        self.assertFalse(result)
        self.assertEqual(RequestTimesOut.retries, 1)

    #   - Misc. request error
    def test_request_httpexception(self):
        # Should return False, NOT throw

        class RequestThrows(BaseHTTPSConnMock):
            retries = 0

            def request(self, *args, **kwargs):
                self.__class__.retries += 1
                raise http_client.HTTPException()
        result = send_signifai.POST_data(auth_key="", data=self.events,
                                         httpsconn=RequestThrows)
        self.assertFalse(result)
        self.assertEqual(RequestThrows.retries, 1)

    #   - Getresponse timeout
    def test_getresponse_timeout(self):
        # Should return False, NOT throw

        class GetResponseTimesOut(BaseHTTPSConnMock):
            def getresponse(self):
                raise socket.timeout

        result = send_signifai.POST_data(auth_key="", data=self.events,
                                         httpsconn=GetResponseTimesOut)
        self.assertFalse(result)

    #   - Misc. getresponse failure
    def test_getresponse_httpexception(self):
        # Should return False, NOT throw

        class GetResponseThrows(BaseHTTPSConnMock):
            def getresponse(self):
                raise http_client.HTTPException()

        result = send_signifai.POST_data(auth_key="", data=self.events,
                                         httpsconn=GetResponseThrows)
        self.assertFalse(result)

    #   - Server error
    def test_post_bad_status(self):
        # Should return False, NOT throw

        class BadStatus(BaseHTTPSConnMock):
            def getresponse(self):
                return BaseHTTPSRespMock("500 Internal Server Error",
                                         status=500)

        result = send_signifai.POST_data(auth_key="", data=self.events,
                                         httpsconn=BadStatus)
        self.assertFalse(result)

    #   - Server sent back non-JSON
    def test_post_bad_response(self):
        # Should return False, NOT throw

        class BadResponse(BaseHTTPSConnMock):
            def getresponse(self):
                return BaseHTTPSRespMock("this is a bad response text",
                                         status=200)

        result = send_signifai.POST_data(auth_key="", data=self.events,
                                         httpsconn=BadResponse)
        self.assertFalse(result)

    # Data correctness failures (all other operations being successful,
    # but the server returned an error/failed event)
    #   - All events fail
    def test_post_bad_corpus(self):
        # Should return False, NOT throw

        class BadContent(BaseHTTPSConnMock):
            def request(self, *args, **kwargs):
                body = kwargs['body']
                self.failed_events = json.loads(body)['events']

            def getresponse(self):
                return BaseHTTPSRespMock(json.dumps({
                    "success": False,
                    "failed_events": self.failed_events
                }))

        result = send_signifai.POST_data(auth_key="", data=self.events,
                                         httpsconn=BadContent)
        self.assertIsNone(result)

    #   - Only some events fail (we treat that as a whole failure)
    def test_post_somebad_somegood(self):
        # Should return False, NOT throw
        events = {"events": [self.corpus, self.corpus]}

        class ReturnsPartialBad(BaseHTTPSConnMock):
            def request(self, *args, **kwargs):
                body = kwargs['body']
                self.failed_events = [{
                    "event": json.loads(body)['events'][1],
                    "error": "some error, doesn't matter"
                }]

            def getresponse(self):
                return BaseHTTPSRespMock(json.dumps({
                    "success": True,
                    "failed_events": self.failed_events
                }))

        result = send_signifai.POST_data(auth_key="", data=events,
                                         httpsconn=ReturnsPartialBad)
        self.assertIsNone(result)

    #   - Ensure request is made as expected based on parameters
    def test_post_request_generation(self):
        # Should return True AND no test case in TestEventGeneration
        # may fail
        test_case = self
        API_KEY = "TEST_API_KEY"

        class TestEventGeneration(BaseHTTPSConnMock):
            def request(self, method, uri, body, headers):
                # This sort of blows encapsulation, but whatever
                test_case.assertEqual(uri, send_signifai.DEFAULT_POST_URI)
                # XXX: json.dumps (or some underlying process) determinism
                #      (specifically, the string may not be generated the
                #      same in both cases due to key/value traversal order,
                #      etc.)
                test_case.assertEqual(body, json.dumps(test_case.events))
                test_case.assertEqual(headers['Authorization'],
                                      "Bearer {KEY}".format(KEY=API_KEY))
                test_case.assertEqual(headers['Content-Type'],
                                      "application/json")
                test_case.assertEqual(headers['Accept'],
                                      "application/json")
                test_case.assertEqual(method, "POST")

            def getresponse(self):
                return BaseHTTPSRespMock(json.dumps({
                    "success": True,
                    "failed_events": []
                }))

        result = send_signifai.POST_data(auth_key=API_KEY, data=self.events,
                                         httpsconn=TestEventGeneration)
        self.assertTrue(result)

    # Success tests
    #   - All is well
    def test_good_post(self):
        # Should return True

        class SucceedsToPOST(BaseHTTPSConnMock):
            def getresponse(self):
                return BaseHTTPSRespMock(json.dumps({
                    "success": True,
                    "failed_events": []
                }))

        result = send_signifai.POST_data(auth_key="", data=self.events,
                                         httpsconn=SucceedsToPOST)
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

        with unittest.mock.patch('datetime.datetime') as MockDT:
            MockDT.now = unittest.mock.MagicMock(return_value=h)

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
