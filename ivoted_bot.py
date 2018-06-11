#!/usr/bin/python3.5

from beem.block import Block
from beem.blockchain import Blockchain
from beem.account import Account
from beem.amount import Amount
from beem.steem import Steem
from steem import Steem as DSteem
import time
from datetime import datetime, timedelta
from dateutil.parser import parse
import MySQLdb as mdb
import threading
import json
import pytz

# MySQL Informations
MySQL_Host = ""
MySQL_User = ""
MySQL_Pass = ""
MySQL_Base = ""

# Account Private Keys
account_keys = ["private_posting_key", "private_active_key"]

# Bot options (Tags and mentions)
account_name = "ivoted"
target_tag = "ivoted"
target_mention = "@ivoted"
target_tagc = "#ivoted"
# Voting Power limit
vp_limit = 95

# Variables for logging purposes
times_run = 0
blocks_checked = 0

# Script variables
last_vote_chk = time.time()
accounts = []
accounts_data = []
number_wv = 0
blocks_treat = []


# Values of the Steem Blockchain used for calculations
def calculate_shares():
    global reward_share, base_share, reward_vesting, steem_per_mvest

    try:
        info = Steem().get_dynamic_global_properties()
        reward_fund = Steem().get_reward_funds()
        total_vests = Amount(info["total_vesting_shares"]).amount
        total_vesting_fund = Amount(info["total_vesting_fund_steem"]).amount
        reward_balance = Amount(reward_fund["reward_balance"]).amount
        recent_claims = float(reward_fund["recent_claims"])
        reward_share = reward_balance / recent_claims
        base_share = Amount(Steem().get_current_median_history()["base"]).amount
        reward_vesting = total_vesting_fund / total_vests
        steem_per_mvest = Steem().get_steem_per_mvest()
        print("- Reward Share and Base Share Actualized")
    except Exception as err:
        print("*Error Calculate Shares : %s" % err)
        pass

    return


# Getting the Voting Power of the account
def get_voting_power(account_data):
    last_vote_time = parse(account_data["last_vote_time"])
    diff_in_seconds = (datetime.utcnow() - last_vote_time).seconds
    regenerated_vp = diff_in_seconds * 10000 / 86400 / 5
    total_vp = (account_data["voting_power"] + regenerated_vp) / 100
    if total_vp > 100:
        return 100
    return "%.2f" % total_vp


# Getting all participants
def get_accounts():
    global accounts, accounts_data, number_wv

    accounts = []
    accounts_data = []
    number_wv = 0

    # Connecting to the MySQL Database
    indic_conn = 0
    while indic_conn == 0:
        try:
            conn = mdb.connect(MySQL_Host, MySQL_User, MySQL_Pass, MySQL_Base, charset='utf8mb4')
            cur = conn.cursor()
            indic_conn = 1
        except (mdb.Error, mdb.Warning):
            time.sleep(0.25)

    # Selecting all accounts
    sql = "SELECT ACCOUNT, VOTED, WITNESS_VOTES_UPDATE, STEEM_POWER FROM ACCOUNTS ORDER BY UID ASC"
    cur.execute(sql)
    data = cur.fetchall()

    # Looping to put values in our local list
    for d in data:
        accounts.append(d[0])
        accounts_data.append({"VOTED": d[1], "WITNESS_VOTES": d[2], "STEEM_POWER": d[3]})
        number_wv += d[2]

    print("- %s accounts" % len(accounts))
    print("- Number of WV : %s" % number_wv)

    # Closing connection
    cur.close()
    conn.close()

    return


# Updating participants' informations
def update_users():
    global accounts, steem_per_mvest, accounts_data

    calculate_shares()

    # Connection à la base de données
    indic_conn = 0
    while indic_conn == 0:
        try:
            conn = mdb.connect(MySQL_Host, MySQL_User, MySQL_Pass, MySQL_Base, charset='utf8mb4')
            cur = conn.cursor()
            indic_conn = 1
        except (mdb.Error, mdb.Warning):
            time.sleep(0.25)

    # Looping through all accounts
    for i, j in enumerate(accounts):
        # Getting SP of the account
        vests_user = Account(j)["vesting_shares"]["amount"] + \
                     Account(j)["received_vesting_shares"]["amount"] - \
                     Account(j)["delegated_vesting_shares"]["amount"]
        sp_voter = vests_user / 1e6 * steem_per_mvest
        wit_votes = 0

        # Getting the number of its witness votes or his proxy's votes
        try:
            wit_proxy = ''
            wit_votes = len(Account(j)["witness_votes"])
            wit_proxy = Account(j)["proxy"]

            if wit_proxy != '':
                wit_votes = len(Account(wit_proxy)["witness_votes"])
        except Exception as err:
            print("*** Error Fetching Witness Votes : %s" % err)

        # Updating the database if the values are different
        if wit_votes != accounts_data[i]["WITNESS_VOTES"] or sp_voter > accounts_data[i]["STEEM_POWER"] + 1\
                or sp_voter < accounts_data[i]["STEEM_POWER"] - 1:
            sql = "UPDATE ACCOUNTS SET UPDATED = %s, WITNESS_VOTES_UPDATE = %s, STEEM_POWER = %s WHERE ACCOUNT = %s"

            try:
                cur.execute(sql, (int(time.time() * 1000), wit_votes, sp_voter, j))
                print("-> Updated %s" % j)
            except mdb.Error as err:
                print("* SQL Error : %s" % err)

    # Closing connection
    cur.close()
    conn.commit()
    conn.close()

    # Actualizing the list of accounts
    get_accounts()

    return


# Function for getting a new block
def get_block():
    global last_idb, idb

    # Getting last irreversible block
    idb = Blockchain().get_current_block_num()

    # If it's a new block
    if idb > last_idb + 1:
        # print("Current Block : %s" % idb)
        for i in range(last_idb + 1, idb, 1):
            threading.Thread(target=treat_block, args=[i]).start()
            time.sleep(0.1)

    return


# Function for treating a block
def treat_block(no):
    global last_idb, idb, blocks_checked, blocks_treat

    # Adding the number of this block to the currently treated list
    if no not in blocks_treat:
        blocks_treat.append(no)

        # If we're missing some blocks, we launch new threads
        while no != (last_idb + 1) and (last_idb + 1) <= idb:
            if (last_idb + 1) in blocks_treat:
                time.sleep(0.2)
            else:
                threading.Thread(target=treat_block, args=[last_idb + 1]).start()
                time.sleep(0.2)

        block_valid = 0
        tries = 0

        # Extracting operations from the block
        while block_valid == 0 and tries < 10:
            try:
                # print("Treating Block %s" % no)
                block_posts = Block(no).ops()
                blocks_checked += 1
                block_valid = 1
            except Exception as e:
                print("*** ERROR IN BLOCK %s (Try %s) : %s" % (no, tries, e))
                block_valid = 0
                tries += 1
                time.sleep(0.1)

                if tries == 10:
                    print("--- Master Error on Block %s" % no)

        # If the extraction worked
        if block_valid == 1:
            for b in block_posts:
                indic_tag = 0
                indic_mention = 0

                # If the operation is a comment
                if b[0] == 'comment':
                    if b[1]["title"] != "" and b[1]["parent_author"] == "":
                        try:
                            # Getting the json_metadata
                            if b[1]['json_metadata'] != '':
                                metadata = json.loads(b[1]['json_metadata'])
                                if target_tag in metadata["tags"]:
                                    print("-> Post with tag")
                                    indic_tag = 1
                        except Exception as err:
                            pass

                    if target_tagc in b[1]['body']:
                        print("-> Body with tag")
                        indic_tag = 1

                    if target_mention in b[1]['body']:
                        print("-> Body with mention")
                        indic_mention = 1

                if indic_tag == 1 or indic_mention == 1:
                    threading.Thread(target=treat_post, args=[b, "TAG"]).start()

                # If we've been proxied votes
                if b[0] == 'account_witness_proxy' and b[1]['proxy'] == account_name:
                    print("-> Been proxied")
                    threading.Thread(target=treat_post, args=[b, "PROXY"]).start()

            # Block is now treated, we remove it from the currently treated blocks
            blocks_treat = list(filter(lambda x: x != no, blocks_treat))
            # print(blocks_treat)

            # Connecting to the database
            indic_conn = 0
            while indic_conn == 0:
                try:
                    conn = mdb.connect(MySQL_Host, MySQL_User, MySQL_Pass, MySQL_Base, charset='utf8mb4')
                    cur = conn.cursor()
                    indic_conn = 1
                except (mdb.Error, mdb.Warning):
                    time.sleep(0.25)

            # Updating the last block number
            sql = "UPDATE LAST_BLOCK SET NUM = %s WHERE UID = 1"
            try:
                cur.execute(sql, (no,))
                last_idb = no
            except mdb.Error as e:
                print("*SQL Error : %S" % e)

            # Closing connection
            cur.close()
            conn.commit()
            conn.close()

            # print("Last Block %s" % last_idb)

            del block_posts

    return


# Treating a post and adding a new participant
def treat_post(data, type):
    global steem_per_mvest

    # Connection à la base de données
    indic_conn = 0
    while indic_conn == 0:
        try:
            conn = mdb.connect(MySQL_Host, MySQL_User, MySQL_Pass, MySQL_Base, charset='utf8mb4')
            cur = conn.cursor()
            indic_conn = 1
        except (mdb.Error, mdb.Warning):
            time.sleep(0.25)

    # Getting the name of the account
    if type == "TAG":
        author = data[1]["author"]
        sql = "INSERT INTO TAGGED VALUES (NULL, %s, %s, %s)"
        try:
            cur.execute(sql, (int(time.time() * 1000), author, data[1]["permlink"]))
        except mdb.Error as err:
            print("* SQL Error : %s" % err)
    elif type == "PROXY":
        author = data[1]["account"]

    # Checking if it is already in the database
    need_insert = 0
    sql = "SELECT ACCOUNT FROM ACCOUNTS WHERE ACCOUNT = %s"
    try:
        cur.execute(sql, (author,))
        res = cur.fetchone()[0]
    except mdb.Error as e:
        print("* Error SQL : %s" % e)
    except TypeError as e:
        need_insert = 1

    # Inserting if not
    if need_insert == 1:
        sql = "INSERT INTO ACCOUNTS VALUES (NULL, %s, %s, %s, 0, %s, %s, %s)"

        vests_user = Account(author)["vesting_shares"]["amount"] + \
                     Account(author)["received_vesting_shares"]["amount"] - \
                     Account(author)["delegated_vesting_shares"]["amount"]
        sp_voter = vests_user / 1e6 * steem_per_mvest

        try:
            wit_votes = len(Account(author)["witness_votes"])
            wit_proxy = Account(author)["proxy"]

            if wit_proxy != '':
                wit_votes = len(Account(wit_proxy)["witness_votes"])
        except Exception as e:
            print("*** Error Fetching Witness Votes : %s" % e)

        try:
            cur.execute(sql, (author, int(time.time() * 1000), int(time.time() * 1000), wit_votes,
                              wit_votes, sp_voter))
            print("-> Inserted %s" % author)
            threading.Thread(target=get_accounts).start()
        except mdb.Error as e:
            print("* SQL Error : %s" % e)

    # Closing connection
    cur.close()
    conn.commit()
    conn.close()

    del data

    return


# The Voting loop
def vote_loop():
    global accounts, accounts_data, vp, number_wv, last_vote_chk, vote_account, vp_limit, account_keys

    while True:
        last_vote_chk = time.time()

        # Checking if we're above the VP limit
        while vp < vp_limit:
            acc_actu = 0
            while acc_actu == 0:
                try:
                    vote_account = Account(account_name)
                    vp = float(get_voting_power(vote_account))
                    acc_actu = 1
                except:
                    time.sleep(5)
                    acc_actu = 0

            print("-> Waiting for VP (%s / %s) to fill up" % (vp, vp_limit))
            time.sleep(300)
            last_vote_chk = time.time()

        # Looping through all accounts and voting
        for i, j in enumerate(accounts):
            last_vote_chk = time.time()
            acc_actu = 0
            while acc_actu == 0:
                try:
                    vote_account = Account(account_name)
                    vp = float(get_voting_power(vote_account))
                    acc_actu = 1
                except:
                    time.sleep(5)
                    acc_actu = 0

            print("-> Voting Power: %s" % vp)

            if vp > vp_limit:
                if int(time.time() * 1000) > accounts_data[i]["VOTED"] + 604800000 \
                        and accounts_data[i]["WITNESS_VOTES"] > 0 and number_wv > 500 and j != account_name:
                    print("/\ Vote %s" % j)
                    tz = pytz.timezone("UTC")
                    dnow = datetime.now()
                    dnow = tz.localize(dnow)
                    last_week = dnow - timedelta(days=7)
                    min_cur = dnow - timedelta(minutes=30)

                    permlink = ''
                    nb_posts = 0
                    nb_comments = 0
                    perm_links = []
                    perm_types = []

                    # Getting history for the account
                    try:
                        history = Account(j).get_account_history(
                            index=10000000000,
                            limit=5000,
                            order=-1,
                            only_ops=['comment'],
                            start=idb,
                            use_block_num=True)

                        for h in history:
                            d = parse(h["timestamp"])
                            dtz = datetime(
                                year=d.year,
                                month=d.month,
                                day=d.day,
                                hour=d.hour,
                                minute=d.minute,
                                second=d.second,
                                tzinfo=pytz.UTC)

                            if min_cur >= dtz >= last_week:
                                if h["parent_author"] == '':
                                    nb_posts += 1
                                    perm_types.append("P")
                                    perm_links.append(h["permlink"])
                                else:
                                    if h["author"] == j:
                                        nb_comments += 1
                                        perm_types.append("C")
                                        perm_links.append(h["permlink"])

                    except Exception as err:
                        print("*Error fetching %s 's posts" % j)

                    # Getting last post or comment
                    try:
                        idp = perm_types.index("P")
                        permlink = perm_links[idp]
                    except Exception as e:
                        try:
                            idc = perm_types.index("C")
                            permlink = perm_links[idc]
                        except Exception as e:
                            permlink = ''

                    # Calculating the upvote strength
                    base_str = (7368 / number_wv)
                    upvote_str = int(base_str * accounts_data[i]["WITNESS_VOTES"] * 10) / 10
                    print("Upvote STR : %s" % upvote_str)

                    if permlink != '':
                        if upvote_str > 0:
                            # Maximum is a 100% vote strength
                            upvote_str = min(upvote_str, 100.0)
                            authperm = '@' + j + '/' + permlink
                            print("Need to vote for %s (%s upvote weight) - %s" % (j, upvote_str, permlink))

                            voted = 0
                            tries = 0

                            # Voting
                            while voted == 0 and tries < 10:
                                try:
                                    conn = DSteem(keys=account_keys)
                                    conn.vote(authperm, upvote_str, account_name)
                                    voted = 1
                                except Exception as e:
                                    print("* Error Connection to Steem : %s" % e)
                                    time.sleep(1)
                                    tries += 1
                                    voted = 0

                            # Recording the vote in the database
                            if voted == 1:
                                # Connecting to the database
                                indic_conn = 0
                                while indic_conn == 0:
                                    try:
                                        conn = mdb.connect(MySQL_Host, MySQL_User, MySQL_Pass, MySQL_Base,
                                                           charset='utf8mb4')
                                        cur = conn.cursor()
                                        indic_conn = 1
                                    except (mdb.Error, mdb.Warning):
                                        time.sleep(0.25)

                                sql = "UPDATE ACCOUNTS SET VOTED = %s WHERE ACCOUNT = %s"

                                try:
                                    cur.execute(sql, (int(time.time() * 1000), j))
                                    print("-> Updated Voted in ACCOUNTS : %s" % j)
                                except mdb.Error as err:
                                    print("* SQL Error : %s" % err)

                                sql = "INSERT INTO VOTES VALUES (NULL, %s, %s, %s, %s)"

                                try:
                                    cur.execute(sql, (int(time.time() * 1000), j, permlink, upvote_str))
                                    print("-> Inserted Vote in VOTES : %s" % j)
                                except mdb.Error as e:
                                    print("* SQL Error : %s" % e)

                                # Closing Connection
                                cur.close()
                                conn.commit()
                                conn.close()

                                time.sleep(60)

                                get_accounts()
            else:
                break

            time.sleep(2)

        time.sleep(10)

    return


if __name__ == '__main__':
    # On start
    # Getting the last block
    idb = Blockchain().get_current_block_num()

    # Connecting to the MySQL Database
    indic_conn = 0
    while indic_conn == 0:
        try:
            conn = mdb.connect(MySQL_Host, MySQL_User, MySQL_Pass, MySQL_Base, charset='utf8mb4')
            cur = conn.cursor()
            indic_conn = 1
        except (mdb.Error, mdb.Warning):
            time.sleep(0.25)

    # Selecting last block treated
    sql = "SELECT NUM FROM LAST_BLOCK WHERE UID = 1"

    try:
        cur.execute(sql)
        res = cur.fetchone()[0]
        loaded = 1
    except TypeError:
        loaded = 0

    if loaded == 1 and res > 0:
        last_idb = res
    else:
        last_idb = Blockchain().get_current_block_num() - 1

    cur.close()
    conn.close()

    print("Last Block : %s" % last_idb)

    get_accounts()
    threading.Thread(target=update_users).start()

    vote_account = Account(account_name)
    vp = float(get_voting_power(vote_account))
    print("-> Voting Power: %s" % vp)

    th_vote = threading.Thread(target=vote_loop)
    th_vote.start()

    # Perpetual loop
    while True:
        dt = datetime.now()

        # Relaunching the vote loop if it crashed
        if time.time() - last_vote_chk > 900:
            th_vote = threading.Thread(target=vote_loop)
            th_vote.start()

        # Checking if there are new blocks
        threading.Thread(target=get_block).start()

        # Updating users' info every hour
        if dt.second == 0 and dt.minute == 0:
            threading.Thread(target=update_users).start()

        # Logging
        if dt.second == 0:
            print("--- %s / Blocks : %s / Posts : %s / Threads : %s"
                  % (dt, blocks_checked, times_run, threading.active_count()))

            times_run = 0
            blocks_checked = 0

        time.sleep(0.99)
