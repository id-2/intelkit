# Copyright (c) 2024 Microsoft Corporation. All rights reserved.
import asyncio
from json import loads
from collections import defaultdict
import numpy as np
import scipy.spatial.distance
import tiktoken
import toolkit.AI.utils as utils
import toolkit.query_text_data.helper_functions as helper_functions
import toolkit.query_text_data.prompts as prompts


async def assess_relevance(
    ai_configuration,
    search_label,
    search_cids,
    cid_to_text,
    question,
    logit_bias,
    relevance_test_budget,
    num_adjacent,
    relevance_test_batch_size,
    test_history,
    progress_callback,
    chunk_callback,
):
    print(f'Assessing relevance for {search_label} with {len(search_cids)} chunks')
    batched_cids = [search_cids[i:i+relevance_test_batch_size]
                      for i in range(0, len(search_cids), relevance_test_batch_size)]
    batched_texts = [[cid_to_text[cid] for cid in batch] for batch in batched_cids]
    batched_messages = [[utils.prepare_messages(prompts.chunk_relevance_prompt, {'chunk': chunk, 'question': question}) 
                        for chunk in batch] for batch in batched_texts]
    is_relevant = False
    for mx, mapped_messages in enumerate(batched_messages):
        cid_batch = batched_cids[mx]
        if len(test_history) + len(mapped_messages) + num_adjacent > relevance_test_budget:
            mapped_messages = mapped_messages[:relevance_test_budget - len(test_history)]
        mapped_responses = await utils.map_generate_text(
            ai_configuration, mapped_messages, logit_bias=logit_bias, max_tokens=1
        )
        num_relevant = process_relevance_responses(
            search_label,
            cid_batch,
            cid_to_text,
            mapped_responses,
            test_history,
            progress_callback,
            chunk_callback
        )
        print(f'Batch {mx+1} of {len(batched_messages)}: {num_relevant} relevant chunks')
        is_relevant = num_relevant > 0
        if not is_relevant: # No relevant chunks found in this batch; terminate early
            break
    return is_relevant

def process_relevance_responses(
        search_label,
        search_cids,
        cid_to_text,
        mapped_responses,
        test_history,
        progress_callback,
        chunk_callback
    ):
    num_relevant = 0
    for r, c in zip(mapped_responses, search_cids):
        if c not in [x[1] for x in test_history]:
            test_history.append((search_label, c, r))
            if r == 'Yes':
                num_relevant += 1
    if progress_callback is not None:
        progress_callback(helper_functions.get_test_progress(test_history))
    relevant_list = [x[1] for x in test_history if x[2] == 'Yes']
    if chunk_callback is not None:
        chunk_callback([cid_to_text[cid] for cid in relevant_list])
    return num_relevant

async def detect_relevant_chunks(
    ai_configuration,
    question,
    cid_to_text,
    cid_to_concepts,
    cid_to_vector,
    hierarchical_communities,
    community_to_label,
    previous_cid,
    next_cid,
    embedder,
    embedding_cache,
    select_logit_bias,
    adjacent_search_steps,
    community_ranking_chunks,
    relevance_test_budget,
    community_relevance_tests,
    relevance_test_batch_size,
    irrelevant_community_restart,
    chunk_progress_callback=None,
    chunk_callback=None,
):
    test_history = []
    all_units = sorted([(cid, vector) for cid, vector in (cid_to_vector.items())], key=lambda x: x[0])


    yes_id = tiktoken.get_encoding('o200k_base').encode('Yes')[0]
    no_id = tiktoken.get_encoding('o200k_base').encode('No')[0]
    logit_bias = {yes_id: select_logit_bias, no_id: select_logit_bias}

    if chunk_progress_callback is not None:
        chunk_progress_callback(helper_functions.get_test_progress(test_history))
        
    aq_embedding = np.array(
        embedder.embed_store_one(
            question, embedding_cache
        )
    )
    relevant, seen, adjacent = helper_functions.test_history_elements(test_history, previous_cid, next_cid, adjacent_search_steps)

    cosine_distances = sorted(
        [
            (cid, scipy.spatial.distance.cosine(aq_embedding, vector))
            for (cid, vector) in all_units if cid not in seen
        ],
        key=lambda x: x[1],
        reverse=False,
    )
    semantic_search_cids = [x[0] for x in cosine_distances]
    print(f'Semantic search cids: {semantic_search_cids[:100]}')

    level_to_community_sequence = {}

    max_level = max([hc.level for hc in hierarchical_communities])
    concept_to_level_to_community = defaultdict(dict)
    level_to_community_to_candidate_cids = defaultdict(lambda: defaultdict(set))
    level_to_community_to_cids = defaultdict(lambda: defaultdict(list))
    level_to_cid_to_communities = defaultdict(lambda: defaultdict(set))
    community_to_parent = {}
    for hc in hierarchical_communities:
        concept_to_level_to_community[hc.node][hc.level] = community_to_label[hc.cluster]
        if hc.parent_cluster is not None:
            community_to_parent[community_to_label[hc.cluster]] = community_to_label[hc.parent_cluster]
    cid_to_level_to_communities = defaultdict(lambda: defaultdict(set))
    for level in range(0, max_level+1):
        for cid, concepts in cid_to_concepts.items():
            for concept in concepts:
                if concept in concept_to_level_to_community.keys():
                    if level in concept_to_level_to_community[concept].keys():
                        community = concept_to_level_to_community[concept][level]
                        cid_to_level_to_communities[cid][level].add(community)
                        level_to_cid_to_communities[level][cid].add(community)
                        level_to_community_to_candidate_cids[level][community].add(cid)
                    else:
                        # use the community from the previous level
                        if level - 1 in concept_to_level_to_community[concept].keys():
                            community = concept_to_level_to_community[concept][level - 1]
                            cid_to_level_to_communities[cid][level].add(community)
                            level_to_cid_to_communities[level][cid].add(community)
                            level_to_community_to_candidate_cids[level][community].add(cid)

        community_sequence = []
        community_mean_rank = []
        
        for community, cids in level_to_community_to_candidate_cids[level].items():
            mean_rank = np.mean(sorted([semantic_search_cids.index(c) for c in cids])[:community_ranking_chunks])
            community_mean_rank.append((community, mean_rank))
        community_sequence = [x[0] for x in sorted(community_mean_rank, key=lambda x: x[1])]
        print(f'Level {level} community sequence: {community_sequence}')
        level_to_community_sequence[level] = community_sequence

        for cid in semantic_search_cids:
            chunk_communities = cid_to_level_to_communities[cid][level]
            if len(chunk_communities) > 0:
                assigned_community = sorted(chunk_communities, key=lambda x: community_sequence.index(x))[0]
                if cid not in level_to_community_to_cids[level][assigned_community]:
                    level_to_community_to_cids[level][assigned_community].append(cid)

    for level, community_to_cids in level_to_community_to_cids.items():
        for community, cids in community_to_cids.items():
            cids.sort(key=lambda x: semantic_search_cids.index(x))

    # Set level -1 as everything in the dataset
    level_to_community_sequence[-1] = ['1']
    level_to_community_to_cids[-1]['1'] = semantic_search_cids
    for concept, level_to_community in concept_to_level_to_community.items():
        level_to_community[-1] = '1'

    for cid, level_to_community in cid_to_level_to_communities.items():
        level_to_community[-1] = '1'
    
    successive_irrelevant = 0
    eliminated_communities = set()
    current_level = -1

    while len(test_history) + len(adjacent) < relevance_test_budget:
        print(f'New level {current_level} loop after {len(test_history)} tests')
        relevant_this_loop = False

        community_sequence = []
        for community in level_to_community_sequence[current_level]:
            if community in community_to_parent.keys():
                parent = community_to_parent[community]
                if parent not in eliminated_communities:
                    community_sequence.append(community)
                else:
                    eliminated_communities.add(community)
                    print(f'Eliminated community {community} due to parent {parent}')
            else:
                community_sequence.append(community)
        print(f'Community sequence: {community_sequence}')
        community_to_cids = level_to_community_to_cids[current_level]
        for community in community_sequence:
            relevant, seen, adjacent = helper_functions.test_history_elements(test_history, previous_cid, next_cid, adjacent_search_steps)
            unseen_cids = [c for c in community_to_cids[community] if c not in seen][:community_relevance_tests]
            if len(unseen_cids) > 0:
                print(f'Assessing relevance for community {community} with chunks {unseen_cids}')
                is_relevant = await assess_relevance(
                    ai_configuration=ai_configuration,
                    search_label=f"topic {community}",
                    search_cids=unseen_cids,
                    cid_to_text=cid_to_text,
                    question=question,
                    logit_bias=logit_bias,
                    relevance_test_budget=relevance_test_budget,
                    num_adjacent=len(adjacent),
                    relevance_test_batch_size=relevance_test_batch_size,
                    test_history=test_history,
                    progress_callback=chunk_progress_callback,
                    chunk_callback=chunk_callback,
                )
                relevant_this_loop |= is_relevant
                print(f'Community {community} relevant? {is_relevant}')
                if current_level > -1 and not is_relevant: # don't stop after failure at the root level
                    eliminated_communities.add(community)
                    successive_irrelevant += 1
                    if successive_irrelevant == irrelevant_community_restart:
                        successive_irrelevant = 0
                        print(f'{successive_irrelevant} successive irrelevant communities; restarting')
                        break
                else:
                    successive_irrelevant = 0
        if current_level > -1 and not relevant_this_loop: # don't stop after failure at the root level
            print('Nothing relevant this loop')
            break
        if current_level + 1 in level_to_community_sequence.keys():
            print('Incrementing level')
            current_level += 1
        else:
            print('Reached final level')

    relevant, seen, adjacent = helper_functions.test_history_elements(test_history, previous_cid, next_cid, adjacent_search_steps)

    await assess_relevance(
        ai_configuration=ai_configuration,
        search_label="neighbours",
        search_cids=adjacent,
        cid_to_text=cid_to_text,
        question=question,
        logit_bias=logit_bias,
        relevance_test_budget=relevance_test_budget,
        num_adjacent=len(adjacent),
        relevance_test_batch_size=relevance_test_batch_size,
        test_history=test_history,
        progress_callback=chunk_progress_callback,
        chunk_callback=chunk_callback,
    )
    relevant, seen, adjacent = helper_functions.test_history_elements(test_history, previous_cid, next_cid, adjacent_search_steps)
    relevant.sort()

    return relevant, helper_functions.get_test_progress(test_history)
