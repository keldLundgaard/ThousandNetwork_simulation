import collections
import matplotlib.pylab as plt
import matplotlib.ticker as ticker
import numpy as np
import igraph as ig
import seaborn as sns
from simulation_data import data
import os


def plt_clear_all():
    plt.clf()
    plt.close()


def plot_age_distribution_over_time(g_states, filename=None):
    num_plots = len(g_states)
    fig = plt.gcf()

    max_cols = 5
    if int(np.ceil(np.sqrt(num_plots))) >= max_cols:
        cols = max_cols
    else:
        cols = int(np.ceil(np.sqrt(num_plots)))

    rows = int(np.ceil(num_plots/cols))

    fig.set_size_inches(14, 5*rows)

    for i, g in enumerate(g_states):

        plt.subplot(rows, int(np.ceil(num_plots/float(rows))), i+1)

        plt.hist(
            g.vs['age'],
            bins=27,
            range=[18, 45],
            normed=True,
            label='t: %i' % i,
        )
        plt.legend()

    if filename:
        plt.savefig(filename)
    fig.clf()


def plot_members_over_time(g_states, filename=None, title=None, show=0):
    plt.clf()

    members = []
    for i, g in enumerate(g_states):
        ages = g.vs['age']
        members.append(len(ages))

    plt.plot(members)

    if title:
        plt.title(title)
    plt.xlabel('Time (years)')
    plt.ylabel('Member count')

    if filename:
        plt.savefig(filename)

    if show:
        plt.show()


def plot_avg_age_over_time(g_states, filename=None):
    plt.clf()

    avg_ages = []
    for i, g in enumerate(g_states):
        ages = g.vs['age']
        avg_ages.append(np.mean(ages))

    plt.plot(
        avg_ages)

    plt.title('Average age over time')
    plt.xlabel('Simulation time (years)')
    plt.ylabel('Average age (years)')

    if filename:
        plt.savefig(filename)


def plot_members_per_city_over_time(g_states, filename=None):
    plt.clf()
    g = g_states[-1]

    cities = list(set(g.vs['city']))

    to_plot_dict = {}
    for city in cities:
        to_plot_dict[city] = []

    for i, gw in enumerate(g_states):
        for city in cities:
            to_plot_dict[city].append(len(gw.vs.select(city=city)))

    for city in cities:
        plt.plot(
            to_plot_dict[city],
            label=city
        )

    plt.xlabel('time')
    plt.ylabel('members')
    plt.legend(loc=4)

    if filename:
        plt.savefig(filename)


def plot_members_degree(
        g,
        filename,
        limit=None,
        title=None,
        show=0):
    plt.clf()
    ax = plt.figure().gca()

    ambassadors_any_time_indexes = set(
        [ambassador.index for ambassador in g.vs.select(ambassador=True)]
        + [former_ambassador.index for former_ambassador
            in g.vs.select(former_ambassador=True)])

    ambassadors_any_time_indexes = list(
        np.sort(np.array(list(ambassadors_any_time_indexes))))

    other_members = np.delete(range(len(g.vs)), ambassadors_any_time_indexes)

    if limit == 'ambassadors_all_times':
        degrees = np.take(g.vs.degree(), ambassadors_any_time_indexes)
    elif limit == 'non_ambassadors':
        degrees = np.take(g.vs.degree(), other_members)
    else:
        degrees = g.vs.degree()
    plt.hist(
        degrees,
        bins=50,
        range=[0, max(g.vs.degree())]
    )
    plt.xlabel('Number of connections')
    plt.ylabel('Member count')
    if title:
        plt.title(title)

    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))

    if show:
        plt.show()
    else:
        plt.savefig(filename)


def do_visuals(g):
    for i, hub_city in enumerate(list(set(g.vs['city']))):
        hub_members = g.vs.select(city=hub_city)
        indexes = [hub_member.index for hub_member in hub_members]
        g.vs(indexes)['color'] = data['css_colors'][i]
        g.vs(indexes)['size'] = 10

        former_ambassador_indexes = [
            hub_member.index for hub_member in hub_members
            if hub_member['former_ambassador']]

        for index in former_ambassador_indexes:
            g.vs(index)['shape'] = 'triangle-up'

        ambassador_index = [
            hub_member.index for hub_member in hub_members
            if hub_member['ambassador']]

        if len(ambassador_index):
            ambassador_index = ambassador_index[0]
            g.vs(ambassador_index)['shape'] = 'rectangle'
            g.vs(ambassador_index)['label'] = hub_city
            g.vs(ambassador_index)['size'] = 15

    return g


def get_visual_style(g):
    visual_style = {}
    visual_style["edge_width"] = [1]
    visual_style["bbox"] = (500, 500)
    visual_style["margin"] = 20

    # Show strong links
    strong_links = [
        int(interactions > 5) for interactions in g.es["interactions"]]

    weak_link_color = '#e0e0d1'
    strong_link_color = '#ffb399'
    edge_widths = []
    edge_colors = []
    for es_index, is_strong in enumerate(strong_links):
        if is_strong:
            edge_colors.append(strong_link_color)
            edge_widths.append(2)
        else:
            edge_colors.append(weak_link_color)
            edge_widths.append(1)

    visual_style["edge_color"] = edge_colors
    visual_style["edge_width"] = edge_widths

    # apply visuals
    g = do_visuals(g)

    return g, visual_style


def plot_graph(
        g,
        filename=None,
        layout=None,
        fruchterman=0,
        delete_zero_connections=1,
        visual_styling={}):

    if delete_zero_connections:
        g.delete_vertices(
            [i for i, degree in enumerate(g.degree()) if degree == 0])

    g, visual_style = get_visual_style(g)

    visual_style.update(visual_styling)
    if layout:
        ig.plot(
            g,
            filename,
            layout=layout,
            **visual_style)

    elif fruchterman:
        ig.plot(
            g,
            filename,
            layout=g.layout_fruchterman_reingold(
                weights=np.array(g.es['weights'])**0.5),
            **visual_style)
    else:
        ig.plot(
            g,
            filename,
            **visual_style)


def hist_shortest_path(g, filename, show=0):

    g.delete_vertices(
        [i for i, degree in enumerate(g.degree()) if degree == 0])

    # print g.degree()
    shortest_paths = g.shortest_paths_dijkstra(mode='all')
    # print shortest_paths
    # ig.plot(g)
    plt.hist(
        np.hstack(shortest_paths),
        range=[0, 5],
        bins=5,
        rwidth=1.,
        align='left',
        normed=True,
    )
    plt.xlabel('Number of steps')
    plt.ylabel('Proportion')

    plt.title(
        'Number of steps to each member (mean: %.2f)'
        % np.mean(shortest_paths))
    if show:
        plt.show()
    else:
        plt.savefig(filename)


def show_graph(g, name):
    g, visual_style = get_visual_style(g)
    ig.plot(g, name+'.png', **visual_style)


def all_plots(
        run_name,
        g_states):

    if not os.path.exists(run_name):
        os.mkdir(run_name)

    plot_age_distribution_over_time(
        g_states,
        filename=run_name+'/time_distribution_change.pdf')

    plot_avg_age_over_time(
        g_states,
        filename=run_name+'/avg_age_over_time.pdf')

    plot_members_over_time(
        g_states,
        filename=run_name+'/members_over_time.pdf')

    plot_members_per_city_over_time(
        g_states,
        filename=run_name+'/members_per_city_over_time.pdf')

    plot_degree_non_ambassadors(
        g_states[-1],
        run_name+'/degree_non_ambassadors.pdf')

    plot_degree_ambassadors(
        g_states[-1], run_name+'/degree_ambassadors.pdf')

    plot_graph(
        g_states[-1],
        filename=run_name+'/graph_end.pdf')
