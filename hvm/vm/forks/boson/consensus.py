from hvm.db.consensus import ConsensusDB
from hvm.rlp.consensus import StakeRewardType2, StakeRewardBundle, NodeStakingScore
from hvm.utils.numeric import stake_weighted_average
from hvm.validation import (
    validate_canonical_address,
    validate_uint256
)

import time
from typing import List, Tuple
from eth_typing import Address, BlockNumber

from hvm.types import Timestamp

from hvm.exceptions import HeaderNotFound, NotEnoughProofsOrStakeForRewardType2Proof
from decimal import Decimal

from eth_utils import to_wei

from hvm.exceptions import ValidationError

REWARD_TYPE_1_AMOUNT_FACTOR = 0 #1 % per year
REWARD_TYPE_2_AMOUNT_FACTOR = Decimal(0.03*1/(60*60*24*365)) #3 % per year for normal nodes

MASTERNODE_LEVEL_1_REQUIRED_BALANCE = to_wei(10000, 'ether')
MASTERNODE_LEVEL_2_REQUIRED_BALANCE = to_wei(75000, 'ether')
MASTERNODE_LEVEL_3_REQUIRED_BALANCE = to_wei(150000, 'ether')

MASTERNODE_LEVEL_1_REWARD_TYPE_2_MULTIPLIER = Decimal(4/3) #4 % per year
MASTERNODE_LEVEL_2_REWARD_TYPE_2_MULTIPLIER = Decimal(6/3) #6 % per year
MASTERNODE_LEVEL_3_REWARD_TYPE_2_MULTIPLIER = Decimal(8/3) #8 % per year

EARLY_BIRD_BONUS_FACTOR = 5 #5 x rewards for the first year
EARLY_BIRD_BONUS_CUTOFF_TIMESTAMP = 1593505425 # Tuesday, June 30, 2020 1:23:45 AM GMT-07:00


TIME_BETWEEN_PEER_NODE_HEALTH_CHECK = 60 * 60  # check the health of connected peers once per hour
MIN_ALLOWED_TIME_BETWEEN_REWARD_BLOCKS = 60*60*24 # once per day
REWARD_BLOCK_CREATION_ATTEMPT_FREQUENCY = 60*30 # retry making a reward block every 30 minutes
REWARD_PROOF_TIMESTAMP_VARIABILITY_ALLOWANCE = 300
REQUIRED_STAKE_FOR_REWARD_TYPE_2_PROOF = MASTERNODE_LEVEL_3_REQUIRED_BALANCE*2
REQUIRED_NUMBER_OF_PROOFS_FOR_REWARD_TYPE_2_PROOF = 2
COIN_MATURE_TIME_FOR_STAKING = 60*60*72 # 72 hours
PEER_NODE_HEALTH_CHECK_RESPONSE_TIME_PENALTY_START_MS = 100 #this is the average response time where the staking score starts to be reduced.
PEER_NODE_HEALTH_CHECK_RESPONSE_TIME_PENALTY_50_PERCENT_REDUCTION_MS = 500 #this is the response time in ms where the staking score is reduced by 50%
#REWARD_BLOCK_AND_BUNDLE_TIMESTAMP_VARIABILITY_ALLOWANCE = 60

# testing
# MIN_ALLOWED_TIME_BETWEEN_REWARD_BLOCKS =10
# REWARD_BLOCK_CREATION_ATTEMPT_FREQUENCY = 10
# REQUIRED_STAKE_FOR_REWARD_TYPE_2_PROOF = 1
# REQUIRED_NUMBER_OF_PROOFS_FOR_REWARD_TYPE_2_PROOF = 1
# TIME_BETWEEN_PEER_NODE_HEALTH_CHECK = 10

class BosonConsensusDB(ConsensusDB):
    reward_type_1_amount_factor = REWARD_TYPE_1_AMOUNT_FACTOR
    reward_type_2_amount_factor = REWARD_TYPE_2_AMOUNT_FACTOR

    masternode_level_3_required_balance = MASTERNODE_LEVEL_3_REQUIRED_BALANCE
    masternode_level_3_multiplier = MASTERNODE_LEVEL_3_REWARD_TYPE_2_MULTIPLIER
    masternode_level_2_required_balance = MASTERNODE_LEVEL_2_REQUIRED_BALANCE
    masternode_level_2_multiplier = MASTERNODE_LEVEL_2_REWARD_TYPE_2_MULTIPLIER
    masternode_level_1_required_balance = MASTERNODE_LEVEL_1_REQUIRED_BALANCE
    masternode_level_1_multiplier = MASTERNODE_LEVEL_1_REWARD_TYPE_2_MULTIPLIER

    peer_node_health_check_response_time_penalty_start_ms = PEER_NODE_HEALTH_CHECK_RESPONSE_TIME_PENALTY_START_MS  # this is the average response time where the staking score starts to be reduced.
    peer_node_health_check_response_time_penalty_50_percent_reduction_ms = PEER_NODE_HEALTH_CHECK_RESPONSE_TIME_PENALTY_50_PERCENT_REDUCTION_MS  # this is the response time in ms where the staking score is reduced by 50%
    time_between_peer_node_health_check = TIME_BETWEEN_PEER_NODE_HEALTH_CHECK # check the health of connected peers once per hour
    min_time_between_reward_blocks = MIN_ALLOWED_TIME_BETWEEN_REWARD_BLOCKS # once per day
    reward_proof_timestamp_variability_allowance = REWARD_PROOF_TIMESTAMP_VARIABILITY_ALLOWANCE
    reward_block_creation_attempt_frequency = REWARD_BLOCK_CREATION_ATTEMPT_FREQUENCY # retry making a reward block every 30 minutes
    required_stake_for_reward_type_2_proof = REQUIRED_STAKE_FOR_REWARD_TYPE_2_PROOF
    required_number_of_proofs_for_reward_type_2_proof = REQUIRED_NUMBER_OF_PROOFS_FOR_REWARD_TYPE_2_PROOF
    coin_mature_time_for_staking = COIN_MATURE_TIME_FOR_STAKING # 72 hours


    def calculate_final_reward_type_2_amount(self, node_staking_score_list: List[NodeStakingScore], at_timestamp: Timestamp = None) -> Tuple[int, List[NodeStakingScore]]:
        '''
        This automatically calculates the highest possible score based on the node_staking_scores provided
        :param node_staking_score_list:
        :return:
        '''

        node_staking_score_list = list(node_staking_score_list)

        if at_timestamp is None:
            at_timestamp = int(time.time())

        wallet_address = node_staking_score_list[0].recipient_node_wallet_address
        node_staking_score_list.sort(key=lambda x: -1*x.score)

        total_stake = 0
        num_proofs = 0
        final_list = []
        item_stake_list = []
        for node_staking_score in node_staking_score_list:
            stake = self.chaindb.get_mature_stake(node_staking_score.sender, self.coin_mature_time_for_staking, timestamp = node_staking_score.timestamp)
            final_list.append(node_staking_score)
            item_stake_list.append((node_staking_score.score, stake))

            total_stake += stake
            num_proofs += 1

            if total_stake >= self.required_stake_for_reward_type_2_proof and num_proofs >= self.required_number_of_proofs_for_reward_type_2_proof:
                break

        if total_stake < self.required_stake_for_reward_type_2_proof or num_proofs < self.required_number_of_proofs_for_reward_type_2_proof:
            raise NotEnoughProofsOrStakeForRewardType2Proof("Total stake = {}, required stake = {}. Num proofs = {}, required num proofs = {}".format(total_stake, self.required_stake_for_reward_type_2_proof, num_proofs, self.required_number_of_proofs_for_reward_type_2_proof))


        final_score = int(stake_weighted_average(item_stake_list))


        fractional_interest = self.reward_type_2_amount_factor * Decimal(final_score / 1000000)

        # print("Calculating type 2 reward amount. final_score = {}, fractional_interest = {}, ".format(final_score,fractional_interest))
        amount = self.calculate_reward_based_on_fractional_interest(wallet_address, fractional_interest, at_timestamp)

        if amount != 0:
            return amount, final_list
        else:
            return 0, []

    def calculate_reward_based_on_fractional_interest(self,  wallet_address: Address, fractional_interest: float, at_timestamp: Timestamp = None, include_masternode_bonus = True) -> int:
        '''
        #
        # Added in different masternode levels
        #
        Here we assume the time period for the reward starts from the latest reward block. This is a valid assumption
        because blocks can only be added to the top of the chain
        :param wallet_address:
        :param fractional_interest:
        :param at_timestamp:
        :return:
        '''
        validate_canonical_address(wallet_address, 'wallet_address')
        validate_uint256(at_timestamp, title="at_timestamp")

        if at_timestamp is None:
            at_timestamp = int(time.time())

        latest_reward_block_number = self.chaindb.get_latest_reward_block_number(wallet_address)
        try:
            since_timestamp = self.chaindb.get_canonical_block_header_by_number(latest_reward_block_number,
                                                                                wallet_address).timestamp
        except HeaderNotFound:
            return 0
        canonical_head_block_number = self.chaindb.get_canonical_head(wallet_address).block_number

        # loop backwards to make things simpler
        calc_to_timestamp = at_timestamp
        amount = 0
        for current_block_number in range(canonical_head_block_number, -1, -1):
            header = self.chaindb.get_canonical_block_header_by_number(BlockNumber(current_block_number), wallet_address)

            header_mature_timestamp = header.timestamp + self.coin_mature_time_for_staking
            # this finds the start of the calculation
            if header_mature_timestamp >= calc_to_timestamp:
                continue

            # this finds the end of the calculation
            if calc_to_timestamp <= since_timestamp:
                break

            # if header_mature_timestamp <= since_timestamp:
            #     break

            if header_mature_timestamp < since_timestamp:
                # if the block is older than the since timestamp, but there is still a small window of coin_mature_time_for_staking to add in.
                time_difference = int(calc_to_timestamp - since_timestamp)
            else:
                time_difference = int(calc_to_timestamp - header_mature_timestamp)

            calc_stake = header.account_balance
            if include_masternode_bonus:
                if calc_stake >= self.masternode_level_3_required_balance:
                    masternode_multiplier = self.masternode_level_3_multiplier
                elif calc_stake >= self.masternode_level_2_required_balance:
                    masternode_multiplier = self.masternode_level_2_multiplier
                elif calc_stake >= self.masternode_level_1_required_balance:
                    masternode_multiplier = self.masternode_level_1_multiplier
                else:
                    masternode_multiplier = 1

                if at_timestamp < EARLY_BIRD_BONUS_CUTOFF_TIMESTAMP:
                    masternode_multiplier = Decimal(masternode_multiplier*EARLY_BIRD_BONUS_FACTOR)
            else:
                masternode_multiplier = 1


            amount += int(time_difference * calc_stake * fractional_interest * masternode_multiplier)
            # print('XXXXXXXXXXXXXXXXXXX')
            # print(amount, time_difference, calc_stake, fractional_interest, masternode_multiplier)

            #print("actual calculation = {} * {} * {} * {}".format(time_difference, calc_stake, fractional_interest, masternode_multiplier))

            calc_to_timestamp = header_mature_timestamp

        # if we are calculating all the way to the genesis block, there will be a small
        # COIN_MATURE_TIME_FOR_STAKING that we missed. however, this window has 0 stake, so it would add nothing
        return int(amount)

    def calculate_final_reward_type_1_amount(self, wallet_address: Address, at_timestamp: Timestamp = None) -> int:
        return 0

