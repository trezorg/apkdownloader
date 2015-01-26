from __future__ import absolute_import
import requests
import functools
from google.protobuf import descriptor
from google.protobuf.internal.containers import RepeatedCompositeFieldContainer
from google.protobuf import text_format
from google.protobuf.message import Message
from . import googleplay_pb2


__all__ = (
    'LoginError',
    'RequestError',
    'GooglePlayAPI',
)

requests.packages.urllib3.disable_warnings()


def check_auth_token(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.has_token():
            self.login()
        return func(self, *args, **kwargs)
    return wrapper


class LoginError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class RequestError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

API_DFE_EXPERIMENTS = [
    "nocache:billing.use_charging_poller",
    "market_emails",
    "buyer_currency",
    "prod_baseline",
    "checkin.set_asset_paid_app_field",
    "shekel_test",
    "content_ratings",
    "buyer_currency_in_app",
    "nocache:encrypted_apk",
    "recent_changes"
]

USER_AGENT = (
    "Android-Finsky/3.7.13 (api=3,"
    "versionCode=8013013,sdk=16,device=crespo,hardware=herring,product=soju)"
)

DOWNLOADER_USER_AGENT = (
    "AndroidDownloadManager/4.1.1 (Linux; U; Android 4.1.1;"
    " Nexus S Build/JRO03E)"
)


API_DEFAULT_HEADERS = {
    "X-DFE-Enabled-Experiments": "cl:billing.select_add_instrument_by_default",
    "X-DFE-Unsupported-Experiments": ",".join(API_DFE_EXPERIMENTS),
    "X-DFE-Client-Id": "am-android-google",
    "User-Agent": USER_AGENT,
    "X-DFE-SmallestScreenWidthDp": "320",
    "X-DFE-Filter-Level": "3",
    "Accept-Encoding": "",
    "Host": "android.clients.google.com"
}


class GooglePlayAPI(object):
    """Google Play Unofficial API Class
    Usual APIs methods are login(), search(), details(), bulkDetails(),
    download(), browse(), reviews() and list().
    toStr() can be used to pretty print the result (protobuf object) of the
    previous methods.
    toDict() converts the result into a dict, for easier introspection."""
    SERVICE = "androidmarket"
    # "https://www.google.com/accounts/ClientLogin"
    URL_LOGIN = "https://android.clients.google.com/auth"
    ACCOUNT_TYPE_GOOGLE = "GOOGLE"
    ACCOUNT_TYPE_HOSTED = "HOSTED"
    ACCOUNT_TYPE_HOSTED_OR_GOOGLE = "HOSTED_OR_GOOGLE"
    API_CONTENT_TYPE = "application/x-www-form-urlencoded; charset=UTF-8"
    DEFAULT_LANG = "ru_RU"
    DEFAULT_DEVICE_COUNTRY = "ru",
    DEFAULT_OPERATOR_COUNTRY = "ru",
    DEFAULT_DEVICE_LANG = "ru",

    def __init__(self, androidId=None, email=None, password=None,
                 auth_sub_token=None, lang=None, debug=False, **kwargs):
        """You must use a device-associated androidId value"""
        if not androidId or not (email and password or auth_sub_token):
            raise ValueError(
                "You should provide at least authSubToken or "
                "(email and password)")
        self.preFetch = {}
        self.androidId = androidId
        self.auth_sub_token = auth_sub_token
        self.debug = debug
        self.lang = lang or self.DEFAULT_LANG
        self.email = email
        self.password = password
        self.device_country = kwargs.get(
            "device_country", self.DEFAULT_DEVICE_COUNTRY)
        self.device_lang = kwargs.get(
            "device_lang", self.DEFAULT_DEVICE_LANG)
        self.operator_country = kwargs.get(
            "operator_country", self.DEFAULT_OPERATOR_COUNTRY)

    def toDictSingle(self, protoObj):
        """
        Converts the (protobuf) result from an API call into a dict, for
        easier introspection.
        """
        msg = {}
        for fielddesc, value in protoObj.ListFields():
            # print value, type(value), getattr(value, "__iter__", False)
            if (fielddesc.type == descriptor.FieldDescriptor.TYPE_GROUP or
                    isinstance(value, RepeatedCompositeFieldContainer) or
                    isinstance(value, Message)):
                msg[fielddesc.name] = self.toDict(value)
            else:
                msg[fielddesc.name] = value
        return msg

    def toDict(self, protoObj):
        """
        Converts the (protobuf) result from an API call into a dict, for
        easier introspection.
        """
        if not isinstance(protoObj, RepeatedCompositeFieldContainer):
            return self.toDictSingle(protoObj)
        retlist = []
        for po in protoObj:
            msg = {}
            for fielddesc, value in po.ListFields():
                # print value, type(value), getattr(value, "__iter__", False)
                if (fielddesc.type == descriptor.FieldDescriptor.TYPE_GROUP or
                        isinstance(value, RepeatedCompositeFieldContainer) or
                        isinstance(value, Message)):
                    msg[fielddesc.name] = self.toDict(value)
                else:
                    msg[fielddesc.name] = value
            retlist.append(msg)
        return retlist

    def toStr(self, protoObj):
        """Used for pretty printing a result from the API."""
        return text_format.MessageToString(protoObj)

    def _try_register_preFetch(self, protoObj):
        fields = [i.name for i, _ in protoObj.ListFields()]
        if ("preFetch" in fields):
            for p in protoObj.preFetch:
                self.preFetch[p.url] = p.response

    def has_token(self):
        return bool(self.auth_sub_token)

    def get_token(self):
        return self.auth_sub_token

    def login(self):
        """
        Login to your Google Account. You must provide either:
        - an email and password
        - a valid Google authSubToken
        """
        params = {
            "Email": self.email,
            "Passwd": self.password,
            "service": self.SERVICE,
            "accountType": self.ACCOUNT_TYPE_HOSTED_OR_GOOGLE,
            "has_permission": "1",
            "source": "android",
            "androidId": self.androidId,
            "app": "com.android.vending",
            "device_country": self.device_country,
            "operatorCountry": self.operator_country,
            "lang": self.device_lang,
            "sdk_version": "16"
        }
        headers = {
            "Accept-Encoding": "",
        }
        response = requests.post(
            self.URL_LOGIN, data=params, headers=headers, verify=False)
        data = response.text.split()
        params = {}
        for d in data:
            if "=" not in d:
                continue
            k, v = d.split("=")
            params[k.strip().lower()] = v.strip()
        if "auth" in params:
            self.auth_sub_token = params["auth"]
        elif "error" in params:
            raise LoginError("server says: " + params["error"])
        else:
            raise LoginError("Auth token not found.")

    def executeRequestApi2(
            self, path, datapost=None, post_content_type=API_CONTENT_TYPE):
        if (datapost is None and path in self.preFetch):
            data = self.preFetch[path]
        else:
            headers = {
                "Accept-Language": self.lang,
                "Authorization": "GoogleLogin auth={0}".format(
                    self.auth_sub_token),
                "X-DFE-Device-Id": self.androidId,
            }
            headers.update(API_DEFAULT_HEADERS)
            if datapost is not None:
                headers["Content-Type"] = post_content_type
            url = "https://android.clients.google.com/fdfe/{0}".format(path)
            if datapost is not None:
                response = requests.post(
                    url, data=datapost, headers=headers, verify=False)
            else:
                response = requests.get(url, headers=headers, verify=False)
            data = response.content
        message = googleplay_pb2.ResponseWrapper.FromString(data)
        self._try_register_preFetch(message)
        return message

    #####################################
    # Google Play API Methods
    #####################################

    @check_auth_token
    def search(self, query, nb_results=None, offset=None):
        """Search for apps."""
        path = "search?c=3&q=%s" % requests.utils.quote(query)
        if (nb_results is not None):
            path += "&n=%d" % int(nb_results)
        if (offset is not None):
            path += "&o=%d" % int(offset)
        message = self.executeRequestApi2(path)
        return message.payload.searchResponse

    @check_auth_token
    def details(self, packageName):
        """
        Get app details from a package name.
        packageName is the app unique ID (usually starting with 'com.').
        """
        path = "details?doc=%s" % requests.utils.quote(packageName)
        message = self.executeRequestApi2(path)
        return message.payload.detailsResponse

    @check_auth_token
    def bulkDetails(self, packageNames):
        """
        Get several apps details from a list of package names.
        This is much more efficient than calling N times details() since it
        requires only one request.
        packageNames is a list of app ID (usually starting with 'com.').
        """
        path = "bulkDetails"
        req = googleplay_pb2.BulkDetailsRequest()
        req.docid.extend(packageNames)
        data = req.SerializeToString()
        message = self.executeRequestApi2(path, data, "application/x-protobuf")
        return message.payload.bulkDetailsResponse

    @check_auth_token
    def browse(self, cat=None, ctr=None):
        """
        Browse categories.
        cat (category ID) and ctr (subcategory ID) are used as filters.
        """
        path = "browse?c=3"
        if (cat is not None):
            path += "&cat=%s" % requests.utils.quote(cat)
        if (ctr is not None):
            path += "&ctr=%s" % requests.utils.quote(ctr)
        message = self.executeRequestApi2(path)
        return message.payload.browseResponse

    @check_auth_token
    def list(self, cat, ctr=None, nb_results=None, offset=None):
        """
        List apps.
        If ctr (subcategory ID) is None, returns a list of valid subcategories.
        If ctr is provided, list apps within this subcategory.
        """
        path = "list?c=3&cat=%s" % requests.utils.quote(cat)
        if (ctr is not None):
            path += "&ctr=%s" % requests.utils.quote(ctr)
        if (nb_results is not None):
            path += "&n=%s" % requests.utils.quote(nb_results)
        if (offset is not None):
            path += "&o=%s" % requests.utils.quote(offset)
        message = self.executeRequestApi2(path)
        return message.payload.listResponse

    @check_auth_token
    def reviews(self, packageName, filterByDevice=False,
                sort=2, nb_results=None, offset=None):
        """
        Browse reviews.
        packageName is the app unique ID.
        If filterByDevice is True, return only reviews for your device.
        """
        path = "rev?doc=%s&sort=%d" % (requests.utils.quote(packageName), sort)
        if (nb_results is not None):
            path += "&n=%d" % int(nb_results)
        if (offset is not None):
            path += "&o=%d" % int(offset)
        if(filterByDevice):
            path += "&dfil=1"
        message = self.executeRequestApi2(path)
        return message.payload.reviewResponse

    @check_auth_token
    def download(self, packageName, versionCode, offerType=1, stream=False):
        """
        Download an app and return its raw data (APK file).
        packageName is the app unique ID (usually starting with 'com.').
        versionCode can be grabbed by using the details() method on the given
        app."""
        path = "purchase"
        data = "ot=%d&doc=%s&vc=%d" % (offerType, packageName, versionCode)
        message = self.executeRequestApi2(path, data)
        url = message.payload.buyResponse.purchaseStatusResponse.\
            appDeliveryData.downloadUrl
        cookie = message.payload.buyResponse.purchaseStatusResponse.\
            appDeliveryData.downloadAuthCookie[0]
        cookies = {str(cookie.name): str(cookie.value)}
        headers = {
            "User-Agent": DOWNLOADER_USER_AGENT,
            "Accept-Encoding": "",
        }
        response = requests.get(
            url, stream=stream, headers=headers, cookies=cookies, verify=False)
        return response
