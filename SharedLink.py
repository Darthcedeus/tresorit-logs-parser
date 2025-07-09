__author__="Humza Ahmad"
"""
Class to represent shared link object
"""

import json

class SharedLink():
    active = ""
    tresor = ""
    creator = ""
    creatorEmail = ""
    linkTarget = ""
    passwordProtected = ""
    openCount = ""
    openCountLimit = ""
    creationDate = ""
    expirationDate = ""
    detailedAccessLogs = ""
    emailVerification = ""
    downloadDisabled = ""
    watermarkType = ""
    watermarkPosition = ""
    emailAllowList = []
    suspensionDate = ""
    linkID = ""
    cooperativeLink = ""

    def __init__(self,
            active = "",
            tresor = "",
            creator = "",
            creatorEmail = "",
            linkTarget = "",
            passwordProtected = "",
            openCount = "",
            openCountLimit = "",
            creationDate = "",
            expirationDate = "",
            detailedAccessLogs = "",
            emailVerification = "",
            downloadDisabled = "",
            watermarkType = "",
            watermarkPosition = "",
            emailAllowList = [],
            suspensionDate = "",
            linkID = "",
            cooperativeLink = ""
        ):
        self.active = active,
        self.tresor = tresor,
        self.creator = creator,
        self.creatorEmail = creatorEmail,
        self.linkTarget = linkTarget,
        self.passwordProtected = passwordProtected,
        self.openCount = openCount,
        self.openCountLimit = openCountLimit,
        self.creationDate = creationDate,
        self.expirationDate = expirationDate,
        self.detailedAccessLogs = detailedAccessLogs,
        self.emailVerification = emailVerification,
        self.downloadDisabled = downloadDisabled,
        self.watermarkType = watermarkType,
        self.watermarkPosition = watermarkPosition,
        self.emailAllowList = emailAllowList,
        self.suspensionDate = suspensionDate,
        self.linkID = linkID,
        self.cooperativeLink = cooperativeLink

    def to_json(self):
        return json.dumps(self.__dict__)
    
    def __str__(self):
        return self.to_json()
    
    def remove_tuples(self):
        self.active = self.active[0]
        self.tresor = self.tresor[0]
        self.creator = self.creator[0]
        self.creatorEmail = self.creatorEmail[0]
        self.linkTarget = self.linkTarget[0]
        self.passwordProtected = self.passwordProtected[0]
        self.openCount = self.openCount[0]
        self.openCountLimit = self.openCountLimit[0]
        self.creationDate = self.creationDate[0]
        self.expirationDate = self.expirationDate[0]
        self.detailedAccessLogs = self.detailedAccessLogs[0]
        self.emailVerification = self.emailVerification[0]
        self.downloadDisabled = self.downloadDisabled[0]
        self.watermarkType = self.watermarkType[0]
        self.watermarkPosition = self.watermarkPosition[0]
        self.emailAllowList = self.emailAllowList[0]
        self.suspensionDate = self.suspensionDate[0]
        self.linkID = self.linkID[0]
        self.cooperativeLink = self.cooperativeLink[0]