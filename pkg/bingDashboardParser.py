#!/usr/bin/env python2

#
# developed by Sergey Markelov (2013)
#

"""
Bing! dashboard page parser

Usage:
    from bingDashboardParser import Reward, parseDashboardPage
    ...
    bingRewards = BingRewards(FACEBOOK_EMAIL, FACEBOOK_PASSWORD)
    bingRewards.authenticate()
    parseDashboardPage(bingRewards.requestDashboardPage(), BING_URL)
"""
import sys
from bs4 import BeautifulSoup
from bingFlyoutParser import RewardV1
from datetime import datetime


class Reward(RewardV1):
    "A class to represent a Bing! reward"


def parseDashboardPage(page, bing_url):
    """
    Parses a bing dashboard page
    returns a list of Reward objects

    page - bing dashboard page - see the class __doc__ for further information
    bing_url - url of bing main page - generally http://www.bing.com which will be
                added to Reward.url as a prefix if appropriate
    """
    reload(sys)
    sys.setdefaultencoding('utf8')

    if page is None: raise TypeError("page is None")
    if page.strip() == "": raise ValueError("page is empty")

    allRewards = []

    # if this is the new type of dashboard page (there's probably a better way to figure this out)
    if page.find("rewards-oneuidashboard") != -1:
        page = page.split("var dashboard")[1]
        # Rewards can be listed more than once so track here and skip those that are already complete
        allTitles = set()
        for attrPair in page.split(',"'):
            current = attrPair.replace('"','').split(':')
            if current[0] == "title":
                currentTitle = current[1].strip()
                if currentTitle in allTitles:
                    #already have this reward, skip it
                    continue
                else:
                    newRwd = Reward()
                    allTitles.add(currentTitle)
                    validRwd = createRewardNewFormat(page, currentTitle, newRwd)
                    if validRwd:
                        allRewards.append(newRwd)

    else:
        #filter out the characters that crash BS (can probably fix this with encoding if someone wants to look into it
        soup = BeautifulSoup(page.replace("&#8212;","").replace("&#10005;","").replace("&#169;","").replace("\u2022","").replace("\u2013","").replace("\u2019",""), 'html.parser')
        rewardsDashboard = soup.find('div', id="dashboard")

        # Get the rewards on the sidebar (mostly search + earn)
        for ddiv in rewardsDashboard.find_all('div', class_='spacer-32-top display-table'):
            appendFirstListReward(allRewards, ddiv)

        # Get the rewards on the main dashboard page
        dashboardOnly = rewardsDashboard.find('div', class_='card-row spacer-32-bottom clearfix')
        links = dashboardOnly.find_all('a')
        i = 0
        while i < len(links):
            appendVariableReward(allRewards, bing_url, i, links)
            i += 1

        appendQuizReward(allRewards, bing_url, rewardsDashboard)

    return allRewards


def appendFirstListReward(allRewards, ddiv):
    currentReward = Reward()
    rewardURL = ''
    rewardName = ''
    rewardProgressCurrent = 0
    rewardProgressMax = 0
    rewardDescription = ''
    lnk = ddiv.find('a')
    if lnk is not None:
        # this url already starts with the bing URL, others need it to be appended
        rewardURL = lnk.get('href')
        rewardName = lnk.get_text()
    progressDiv = ddiv.find('div', class_='text-caption spacer-16-top')
    if progressDiv is not None:
        if foundText(progressDiv, 'of'):
            progressStuff = progressDiv.get_text().split(' ')
            rewardProgressCurrent, rewardProgressMax = int(progressStuff[0]), int(progressStuff[2])
    descriptionDiv = ddiv.find('div', class_='spacer-12-top')
    if descriptionDiv is not None:
        rewardDescription = descriptionDiv.get_text()
    createReward(currentReward, rewardURL, rewardName, rewardProgressCurrent, rewardProgressMax, rewardDescription)
    allRewards.append(currentReward)


def appendVariableReward(allRewards, bing_url, i, links):
    currentReward = Reward()
    rewardProgressCurrent = 0
    rewardProgressMax = 0
    # need to append the bing url here
    rewardURL = bing_url + links[i].get('href')
    rewardName = links[i].find('div', class_='offer-title-height')
    # if this reward has not been started
    rewardDescription = links[i].find('div', class_='offer-description-height spacer-20-top ')
    # 'HIT' rewards will have their point total in this field
    currAction = links[i].find('span', class_='pull-left card-button-line-height margin-right-15')
    # if the reward is a quiz and partially complete
    if rewardDescription is None:
        rewardDescription = links[i].find('div', class_='text-caption progress-text-height clearfix')
        if foundText(rewardDescription, 'of'):
            progressStuff = rewardDescription.get_text().split(' ')
            rewardProgressCurrent, rewardProgressMax = int(progressStuff[0]), int(progressStuff[2])
            # also need to find the new description here
            rewardDescription \
                = links[i].find('div',
                                class_='offer-description-height spacer-20-top offer-description-margin-bottom')
            # if the reward is a quiz and fully complete
    if foundText(rewardDescription, 'You did it!'):
        rDscSplit = rewardDescription.get_text().replace('\n', '').split(' ')
        rewardProgressCurrent = rewardProgressMax = int(rDscSplit[rDscSplit.index('points.') - 1].replace(',', ''))
        # Grab the point totals for 'HIT' rewards - we're using these as a marker to set the 'HIT' type
    hits = checkForHit(currAction, rewardProgressCurrent, rewardProgressMax, links[i])
    if hits is not None:
        rewardProgressCurrent, rewardProgressMax = hits[0], hits[1]
    createReward(currentReward, rewardURL, rewardName.get_text(), rewardProgressCurrent, rewardProgressMax,
                 rewardDescription.get_text())
    allRewards.append(currentReward)


def appendQuizReward(allRewards, bing_url, rewardsDashboard):
    # Get the top feature reward (top spot on the dashboard) - doing this separately since it's hard to parse as part of the dashboard
    # first link on the dashboard will be the top spot
    currentReward = Reward()
    rewardProgressCurrent = 0
    rewardProgressMax = 0
    topLink = rewardsDashboard.find('a')
    # need to append the bing url here
    rewardURL = bing_url + topLink.get('href')
    rewardName = topLink.find('div', class_='offer-title-height')
    rewardDescription = topLink.find('div', class_='offer-description-height spacer-20-top ')
    # if the reward is a quiz and partially complete
    if rewardDescription is None:
        rewardDescription = topLink.find('div', class_='text-caption progress-text-height clearfix')
        if foundText(rewardDescription, 'of'):
            progressStuff = rewardDescription.get_text().split(' ')
            rewardProgressCurrent, rewardProgressMax = int(progressStuff[0]), int(progressStuff[2])

            # also need to find the new description here
            rewardDescription \
                = topLink.find('div', class_='offer-description-height spacer-20-top offer-description-margin-bottom')
    # if the reward is a quiz and fully complete
    if foundText(rewardDescription, 'You did it!'):
        rDscSplit = rewardDescription.get_text().split(' ')
        rewardProgressCurrent = rewardProgressMax = int(rDscSplit[rDscSplit.index('points.') - 1])
    currAction = topLink.find('span', class_='pull-left card-button-line-height margin-right-15')
    # Grab the point totals for 'HIT' rewards - we're using these as a marker to set the 'HIT' type
    hits = checkForHit(currAction, rewardProgressCurrent, rewardProgressMax, topLink)
    if hits is not None:
        rewardProgressCurrent, rewardProgressMax = hits[0], hits[1]
    createReward(currentReward, rewardURL, rewardName.get_text(), rewardProgressCurrent, rewardProgressMax,
                 rewardDescription.get_text())
    allRewards.append(currentReward)


def foundText(description, pattern):
    return description.get_text().find(pattern) != -1


def checkForHit(currAction, rewardProgressCurrent, rewardProgressMax, searchLink):
    if currAction is not None:
        if rewardProgressCurrent == 0 and rewardProgressMax == 0:
            if currAction.get_text().lower().find('points') != -1:
                rewardProgressMax = int(currAction.get_text().split(' ')[0])
                # Use the button div to determine whether the offer has been completed
                btn = searchLink.find('div',
                                      class_='card-button-height text-caption text-align-center offer-complete-card-button-background border-width-2 offer-card-button-background')
                if btn is not None:
                    rewardProgressCurrent = rewardProgressMax
                return [rewardProgressCurrent, rewardProgressMax]

def createReward(reward, rUrl, rName, rPC, rPM, rDesc):
    reward.url = rUrl.strip()
    reward.name = rName.strip().encode('latin-1', 'ignore')
    reward.progressCurrent = rPC
    reward.progressMax = rPM
    reward.description = rDesc.strip().encode('latin-1', 'ignore')
    if rPC == rPM:
        reward.isDone = True

    for t in Reward.Type.ALL:
        if t[Reward.Type.Col.ISRE]:         # regex
            if t[Reward.Type.Col.NAME].search(reward.name) \
                and ( t[Reward.Type.Col.DESCRIPTION] is None \
                      or t[Reward.Type.Col.DESCRIPTION] == reward.description ):
                            reward.tp = t

        elif t[Reward.Type.Col.NAME].lower() == reward.name.lower() \
                and ( t[Reward.Type.Col.DESCRIPTION] is None \
                      or t[Reward.Type.Col.DESCRIPTION] == reward.description ):
                            reward.tp = t

    #for 'HIT' rewards (10 points) we assume 10 points, higher values won't be triggered
    #To determine whether a hit is already complete, there is logic above to check which div the button uses + the comparison below
    if reward.progressMax == 10 and reward.progressCurrent != 10:
        reward.tp = Reward.Type.RE_EARN_CREDITS 

def createRewardNewFormat(page, title, newRwd):
    curDate = datetime.now()
    isValid = True
    rewardURL = ''
    rewardName = ''
    rewardProgressCurrent = 0
    rewardProgressMax = 0
    rewardDescription = ''
    #We're going to use this as at trigger to determine whether to process the reward or throw it out. If there is no "complete" attribute (true/false) then ignore the reward
    hasComplete = -1
    relevantSegment = page[page.index(title):]
    relevantSegment = relevantSegment[:relevantSegment.index("}")]
    rewardName = cleanString(title)
    #check relevant segment for 'slide_0', if exists switch to slide processing branch - ignoring for now since I'm not sure slides are rewards
    if relevantSegment.find("slide_") == -1:
        for attrPair in relevantSegment.split(',"'):
            current = attrPair.replace('"','').split(':')
            attrType = current[0].strip().replace('"','')
            #usually just 'description' but some rewards use slide prefix ex: slide_1_description, slide_2_description. Might be better to use regex here
            if attrType == "description":
                rewardDescription = cleanString(current[1])
            if attrType == "progress":
                rewardProgressCurrent = int(cleanString(current[1]))
            if attrType == "max":
                rewardProgressMax = int(cleanString(current[1]))
            if attrType == "destination":
                #since we are splitting on colons the URL is getting split. Need to put it back together here
                if len(current[1]) > 0:
                    if current[1] == 'https' or current[1] == 'http':
                        rewardURL = cleanString(current[1]+':'+current[2])
                    else:
                        rewardURL = cleanString(current[1])
            if attrType == "daily_set_date" != -1:
                #if this reward is not for today (sneak peek rewards are tomorrow), we don't want it
                if len(current[1]) > 0:
                    attrDateObj = datetime.strptime(cleanString(current[1]), '%m/%d/%Y')
                    if not (attrDateObj.year == curDate.year and attrDateObj.month == curDate.month and attrDateObj.day == curDate.day):
                        isValid = False
            if attrType == "complete":
                if current[1] == 'True':
                    hasComplete = 1
                if current[1] == 'False':
                    hasComplete = 0
                #this is the last value, once we get it we have everything we need so break
                break

    #if it isn't completeable then it probably isn't a reward, so ignore it
    if hasComplete == -1:
        isValid = False
    if isValid:
        createReward(newRwd, rewardURL, rewardName, rewardProgressCurrent, rewardProgressMax, rewardDescription)
    return isValid

def cleanString(strToClean):
    return strToClean.replace("\u0027","'").replace("\u0026","&")