# bot.py
from email import message
import os
from webbrowser import get
import discord
import pandas as pd
import json
import requests
from discord.ext import tasks
from dotenv import load_dotenv
from github import Github
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

# Get our block frost api key from the file .env
api_key = os.getenv('BLOCKFROST_API_KEY')

from blockfrost import BlockFrostApi, ApiError, ApiUrls

api = BlockFrostApi(
	project_id=api_key,
	base_url=ApiUrls.mainnet.value,
)




# Get our github api key from the file .env
# Then check login to github

personal_access_token = os.getenv('GITHUB_PERSONAL_TOKEN')
# using an access token
g = Github(personal_access_token)

# Check that we can access the github api and returns correct user
try:   
    user = g.get_user()
    print(user.name)
except ApiError as e:
    print(e)



###################################################################################################

# Get all the pool ids from the armada alliance github repo
# Let's get the armada-alliance repo
repo = g.get_repo('armada-alliance/armada-alliance')

# Get contents of a file in the repo
contents = repo.get_contents("/services/website/content/en/stake-pools")
stake_pools = [x.name for x in contents]
stake_pools_no_extensions = [x.replace('.md', '') for x in stake_pools]

# We have to use blockfrost for now since the hex values I can not convert to bech32 without cli..

# Use the blockfrost api to get the stake pools data

def get_stake_pool_data(hex_pool_id):
        
        if len(hex_pool_id) == 0:
                return "Please enter a non empty list of hex pool ids"
        pool_data_df = pd.DataFrame()
        
        for i in hex_pool_id:
                try:
                        pool_data = api.pool(pool_id=i, return_type='pandas')
                        pool_data_df = pd.concat([pool_data_df,pool_data], axis=0, join='outer')
                
                except ApiError as e:
                        print(e)
                
        index = pd.Index(range(0,len(pool_data_df)))
        pool_data_df.set_index(index, inplace=True)
        return pool_data_df


pool_data_df = get_stake_pool_data(stake_pools_no_extensions)
armada_pool_ids = list(pool_data_df.pool_id)



# Let's get the data from our list of pools by pool id

def query_tip():
        pd_chain_tip = pd.DataFrame()
        url = "https://api.koios.rest/api/v0/tip"
        response = requests.get(url)
        print(response.status_code)
        if response.status_code == 200:
                chain_tip = response.json()
                pd_chain_tip = pd.DataFrame(chain_tip)
                return pd_chain_tip
        
        return response.status_code

# df_tip = query_tip()


# Look up latest block information
# Look Up information about specific Blocks made by a pool

def get_block_info(block_hash_list, content_range="0-999"):
        
        
        data_payload = {"_block_hashes": block_hash_list}
        headers = {'Range': content_range}
        reqs = requests.post('https://api.koios.rest/api/v0/block_info', headers=headers, json=data_payload)
        print(reqs.status_code)
        if reqs.status_code == 200:
                block_info = reqs.json()
                pd_block_info = pd.DataFrame(block_info)
                return pd_block_info

        return reqs.status_code


# Get the latest blocks list
def get_block_list(content_range="0-999"):
        
        
        headers = {'Range': content_range}
        reqs = requests.get('https://api.koios.rest/api/v0/blocks', headers=headers)
        print(reqs.status_code)
        if reqs.status_code == 200:
                block_info = reqs.json()
                pd_block_info = pd.DataFrame(block_info)
                return pd_block_info

        return reqs.status_code


# Get Pool info by pool id

def get_pool_info(pool_list, content_range="0-999"):

        
        data_payload = {"_pool_bech32_ids": pool_list}
        headers = {'Range': content_range}
        reqs = requests.post('https://api.koios.rest/api/v0/pool_info', headers=headers, json=data_payload)
        print(reqs.status_code)
        if reqs.status_code == 200:
                pool_info = reqs.json()
                pd_pool_info = pd.DataFrame(pool_info)
                return pd_pool_info

        return reqs.status_code

armada_pools_df = get_pool_info(armada_pool_ids)

tickers = []
for i in range(len(armada_pools_df)):
        
        if type(armada_pools_df.meta_json[i]) != type(None):
                tickers.append(armada_pools_df.meta_json[i]['ticker']) 
                
        else:
                tickers.append('NONE{}'.format(i))
                
armada_pools_df['ticker'] = tickers

###################################################################################################

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@tasks.loop(seconds=24)
async def test():
        
        channel = client.get_channel("Insert Discord Channel ID")
        messages = [msg async for msg in channel.history(limit=1)]
        contents = [message.content for message in messages]
        
        
        # Get Data of last 3 blocks every few seconds
        latest_5_blocks = get_block_list(content_range="0-2")
        
        if type(latest_5_blocks) == type(pd.DataFrame()):
                
                if len(latest_5_blocks) > 0:
                        print("Latest Block Hash: {}\nBlock Height No: {}\nMade By Pool: {}"
                              .format(latest_5_blocks.hash[0],latest_5_blocks.block_height[0],latest_5_blocks.pool[0]))
                
                        for block in range(len(latest_5_blocks)):
                                if latest_5_blocks.pool[block] in armada_pool_ids:
                                        print("AHOY!")
                                        
                                        ticker = armada_pools_df[armada_pools_df['pool_id_bech32'] == latest_5_blocks.pool[block]].ticker.values[0]
                                        pool_id_hex = armada_pools_df[armada_pools_df['pool_id_bech32'] == latest_5_blocks.pool[block]].pool_id_hex.values[0] 
                                        
                                        message="""
                                        **Ahoy! More Plunder** 🏴‍☠️
                                        \n**New Block** 🧱 **added to** ***{}*** **pool's treasure chest**💰
                                        \n🪪**Pool ID:** ***{}***
                                        \n#️⃣**Hash:** ***{}***
                                        \n🕰**Epoch:** ***{}*** 🔢**Height_No:** ***{}***
                                        \n📏**Size**: ***{}*** 🔢**Number of Tx:** ***{}***
                                        \n🧱**Info:** https://cexplorer.io/block/{}
                                        \n🎱**Pool Info:** https://armada-alliance.com/stake-pools/{}
                                        """.format(ticker,
                                                   latest_5_blocks.pool[block],
                                                   latest_5_blocks.hash[block],
                                                   latest_5_blocks.epoch[block],
                                                   latest_5_blocks.block_height[block],
                                                   latest_5_blocks.block_size[block],
                                                   latest_5_blocks.tx_count[block],
                                                   latest_5_blocks.hash[block], 
                                                   pool_id_hex
                                                   )
                                        for i in contents:
                                                if i.__contains__(latest_5_blocks.hash[block]) == False:
                                                        await channel.send(message)
                                                        print("Discord Message Sent")

@client.event
async def on_ready():
        if not test.is_running():
                test.start()



client.run(TOKEN)