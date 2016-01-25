import numpy as np
import igraph as ig
import copy
import pickle
import os


def initialize_world(config):
    g = ig.Graph()

    hub_cities = config.get('hub_cities', [str(i) for i in range(5)])
    for i, hub_city in enumerate(hub_cities):
        hub_members = int(
            config.get('hub_starting_members_avg', 20)
            + config.get('hub_starting_members_std', 0)*np.random.randn())
        indexes = range(len(g.vs), len(g.vs) + hub_members)
        g.add_vertices(hub_members)
        g.vs(indexes)['city'] = hub_city

        g.vs(indexes)['previous_city'] = None
        g.vs(indexes)['age'] = (
            config.get('mean_starting_age', 24)
            + config.get('starting_age_std', 2)*np.random.randn(len(indexes)))
        g.vs['former_ambassador'] = None
        g.es["interactions"] = 0
    return g


def promote_ambassadors(g, config):
    for i, hub_city in enumerate(list(set(g.vs['city']))):

        hub_members = g.vs.select(city=hub_city)
        indexes = [hub_member.index for hub_member in hub_members]

        if all(v == 0 for v in hub_members.degree()):
            new_ambassador_index = np.random.choice(indexes)
        else:
            old_ambasader_index = [
                hub_member.index for hub_member in hub_members
                if hub_member['ambassador']]

            if len(old_ambasader_index):
                if not config.get('promote_new_ambassador_yearly', 0):
                    continue

            g.vs[old_ambasader_index]['ambassador'] = None
            g.vs[old_ambasader_index]['former_ambassador'] = True

            # electing a ambassador with the percentage chance
            # given by how square of degree for each member
            degrees = np.array(hub_members.degree())
            new_ambassador_index = np.random.choice(
                indexes,
                p=(
                    degrees**config.get('degree_count_power', 1.0)
                    / np.sum(degrees**config.get('degree_count_power', 1.0))))

        g.vs(new_ambassador_index)['ambassador'] = True
    return g


def adding_edge(g, link):
    # adding edge to the graph if it does not exists,
    # or doing other things with it
    try:
        new_link = 0
        es_id = g.get_eid(link[0], link[1])
    except:
        new_link = 1
        # no such edge: adding one
        g.add_edges([link])
        es_id = len(g.es)-1

    if new_link:
        g.es[es_id]['interactions'] = 1
        g.es[es_id]['yearly_interactions'] = 1
    else:
        g.es[es_id]['interactions'] += 1
        g.es[es_id]['yearly_interactions'] += 1

    return g


def new_members(g, config):
    for i, hub_city in enumerate(list(set(g.vs['city']))):
        hub_members = g.vs.select(city=hub_city)
        num_new_members = int(
            np.ceil(config.get('new_member_ratio', 0)*len(hub_members)))
        new_members_ids = list(len(g.vs)+np.array(range(num_new_members)))
        g.add_vertices(new_members_ids)
        g.vs(new_members_ids)['city'] = hub_city
        rand_n = np.random.randn(len(new_members_ids))
        g.vs(new_members_ids)['age'] = (
            config.get('mean_starting_age', 24)
            + config.get('starting_age_std', 2)*rand_n)
    return g


def churn(g, config):
    degrees = np.array(g.vs.degree())

    # chance of leaving organization
    chance_of_leaving = (
        config.get('churn_no_degree_rate', 0.0)
        / (degrees+1.)**config.get('degree_count_power', 1.0)
        + config.get('base_churn', 0.0))

    # some members will leave because they know nobody
    # print chance_of_leaving
    if np.sum(chance_of_leaving) != 0.:

        members_leaving = int(np.sum(chance_of_leaving))
        # Normalize so that all weights sum to 1
        chance_of_leaving = chance_of_leaving/np.sum(chance_of_leaving)

        members_leaving = np.random.choice(
            range(len(g.vs)),
            size=members_leaving,
            p=chance_of_leaving)

        g.delete_vertices(members_leaving)

    # Members leave as they get too old for the network
    old_members = g.vs.select(age_gt=config.get('max_age', 100))

    g.delete_vertices([
        old_member.index for old_member in old_members])

    return g


def city_hopping(g, config):
    # people who move:
    people_who_move = np.random.choice(
        range(len(g.vs)),
        int(len(g.vs)*config.get('city_hopping_propability', 0.0)),
        replace=False)

    cities = list(set(g.vs['city']))

    for person_index in people_who_move:
        g.vs[person_index]['previous_city'] = g.vs[person_index]['city']
        g.vs[person_index]['city'] = np.random.choice(cities)

    if config.get('verbose') > 1:
        if config.get('city_hopping_propability') is None:
            print 'warning', 'city_hopping_propability', 'is not defined'

    return g


def global_retreat(g, config):
    all_indexes = range(len(g.vs))
    ambassadors = g.vs.select(ambassador=True)
    index_ambassadors = [ambassador.index for ambassador in ambassadors]
    not_ambassadors = all_indexes
    for i in index_ambassadors:
        not_ambassadors.remove(i)

    number_of_not_ambassadors_goers = (
        config.get('global_retreat_goers', int(len(g.vs)/5.))-len(ambassadors))
    if number_of_not_ambassadors_goers > 0:
        not_ambassadors_going_to_retreat = list(np.random.choice(
            not_ambassadors, number_of_not_ambassadors_goers))
        going_to_retreat = not_ambassadors_going_to_retreat + index_ambassadors
    else:
        going_to_retreat = index_ambassadors

    # make links among participants
    new_links = np.random.choice(
        going_to_retreat,
        (
            config.get('global_retreat_link_multiplier', 10)
            * len(going_to_retreat), 2),
        replace=True)

    for link in new_links:
        if link[0] != link[1]:
            g = adding_edge(g, link)

    return g


def local_event(g, config):
    for hub_city in list(set(g.vs['city'])):
        hub_members = g.vs.select(city=hub_city)

        ambassador_index = [
            hub_member.index for hub_member in hub_members
            if hub_member['ambassador']][0]

        hub_member_indices = [
            hub_member.index for hub_member in hub_members
            if not hub_member['ambassador']]

        event_participants = [ambassador_index]+list(np.random.choice(
            hub_member_indices,
            config.get('local_event_participants', len(hub_members))-1,
            replace=False))

        new_links = np.random.choice(
            event_participants,
            (
                config.get('local_event_avg_new_link_per_participant', 10)
                * len(event_participants), 2),
            replace=True)

        for link in new_links:
            if link[0] != link[1]:
                g = adding_edge(g, link)

        if config.get('verbose', 0) > 1:
            print len(g.es)

    return g


def get_connectivity(g):

    g.delete_vertices(
        [i for i, degree in enumerate(g.degree()) if degree == 0])

    # print g.degree()
    shortest_paths = g.shortest_paths_dijkstra(mode='all')

    return np.mean(shortest_paths)


def run_simulation(config, g_initialize=None):
    if config.get('verbose'):
        print 'Initializing network'

    if not g_initialize:
        g = initialize_world(config)

    g_states = []
    avg_age = []
    num_members = []

    for j in range(config.get('simulation_years', 1)):
        g.es['yearly_interactions'] = 0

        if config.get('verbose', 0) > 0:
            print 'year', str(j),
            print 'members', len(g.vs),
            print 'avg_age: %.1f' % np.mean(g.vs['age'])

        # Saving state -- inefficient as there are no immutable datastructures
        # https://github.com/igraph/igraph/wiki/Temporal-graphs
        if config.get('save_states', 1):
            g_states.append(copy.copy(g))

        avg_age.append(np.mean(g.vs['age']))
        num_members.append(len(g.vs))

        g = city_hopping(g, config)

        g = promote_ambassadors(g, config)

        g = new_members(g, config)

        for i in range(config.get('yearly_local_events', 0)):
            g = local_event(g, config)

        for i in range(config.get('yearly_global_retreats', 0)):
            g = global_retreat(g, config)

        g = churn(g, config)

        if config.get('verbose', 0) > 1:
            print 'members after churn', str(len(g.vs))

        g.vs['age'] = list(np.array(g.vs['age'])+1.)

        if config.get('verbose', 0) > 1:
            print 'yearly interactions', len(g.es['yearly_interactions'])

    # post processing
    g.es['weights'] = g.es['interactions']

    if config.get('delete_zero_connection_at_end', 0):
        # Removing all members without any connections
        g.delete_vertices(
            [i for i, degree in enumerate(g.degree()) if degree == 0])

    if config.get('verbose', 0) > 0:
        print 'end    ',
        print 'members', len(g.vs),
        print 'avg_age: %.1f' % np.mean(g.vs['age'])
        print ' -- stopping simulations -- '

    # saving last iteration
    if config.get('save_states', 1):
        g_states.append(copy.copy(g))

    return g, g_states


def run_simulation_cached(
        config,
        name,
        redo=False,
        simu_folder='simu_archieve'):

    filepath = os.path.join(simu_folder, name+'.pckl')
    if os.path.exists(filepath) and not redo:
        g_states = pickle.load(open(filepath, 'rb'))
    else:
        if not len(simu_folder) and os.path.exists(simu_folder):
            os.mkdir(simu_folder)

        _, g_states = run_simulation(config)
        pickle.dump(g_states, open(filepath, 'wb'))

    return g_states
