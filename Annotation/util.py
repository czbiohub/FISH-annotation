""" 
This module contains utilities used by the spot annotation analysis pipeline.
"""

# ----- #

import numpy as np

import math
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import scipy

from numpy import genfromtxt
from matplotlib.lines import Line2D
from skimage import filters
from sklearn.cluster import AffinityPropagation
from sklearn.cluster import KMeans
from sklearn import metrics
from sklearn.neighbors import KDTree

# ----- #

# colors used by plotters
colors = ['#3399FF', '#CC33FF', '#FFFF00', '#FF33CC', 
'#9966FF', '#009999', '#99E3FF', '#B88A00', 
'#33FFCC', '#FF3366', '#F5B800', '#FF6633',
'#FF9966', '#FF9ECE', '#CCFF33', '#FF667F',
'#EB4E00', '#FFCC33', '#FF66CC', '#33CCFF', 
'#ACFF07', '#667FFF', '#FF99FF', '#FF1F8F',
'#9999FF', '#99FFCC', '#FF9999', '#91FFFF',
'#8A00B8', '#91BBFF', '#FFB71C', '#FF1C76']

"""
Dataframe manipulation
"""

def print_head(df):
	""" Print the first five lines of df 
	"""
	print(df.head(n=5))

def get_workers(df):
	""" Return a numpy array of unique workers in df 
	"""
	uid_list = df.loc[:, ['worker_id']]
	return np.unique(uid_list)

def get_images(df):
	""" Return a numpy array of unique image filenames in df 
	"""
	img_list = df.loc[:, ['image_filename']]
	return np.unique(img_list)

def get_timestamps(df):
	""" Return a list of timestamps in df 
	"""
	matrix = df.loc[:, ['timestamp']].as_matrix()
	return [x[0] for x in matrix]

def slice_by_worker(df, uid):
	""" Return a dataframe with annotations for only one worker

	Parameters
	----------
	df : pandas dataframe
	uid : user ID of worker

	Returns
	-------
	Dataframe with annotations for only that worker 
	"""
	return df[df.worker_id == uid]

# def slice_by_image(df, img_filename):
# 	""" Return a dataframe with annotations for one image

# 	Parameters
# 	----------
# 	df : pandas dataframe
# 	img_filename : string filename of image

# 	Returns
# 	-------
# 	Dataframe with annotations for only that image 
#	
#	No longer useful because each qa object gets data from only one image

# 	"""
# 	return df[df.image_filename == img_filename]

def get_click_properties(df):
	""" Return a numpy array containing properties for all clicks in df

	Parameters
	----------
	df : pandas dataframe

	Returns
	-------
	numpy array
		each row corresponds with one annotation in the dataframe
		columns:
			x coord
			y coord
			time spent (time_spent = 0 indicates first click of an occasion (fencepost case))
			string worker ID
	"""
	occasions = np.unique(df.loc[:, ['time_when_completed']].as_matrix())			# get the list of occasions
	to_return = np.array([]).reshape(0,4)
	for occasion in occasions:
		one_occasion_df = df[df.time_when_completed == occasion]							
		one_occasion_array = one_occasion_df.loc[:, ['x', 'y', 'timestamp', 'worker_id']].as_matrix()
		for i in range(len(one_occasion_array)-1, -1, -1):
			if(i==0):
				time_spent = 0
			else:
				time_spent = one_occasion_array[i][2] - one_occasion_array[i-1][2]
			one_occasion_array[i][2] = time_spent
		to_return = np.vstack([to_return, one_occasion_array])
	return to_return

"""
Other data structure manipulation
"""

def flip(vec, height):
	""" Flip the values of a list about a height
	Useful for flipping y axis to plotting over an image with a flipped coordinate system.

	Parameters
	----------
	vec : list of values to be flipped
	height : height about which to flip values

	Returns
	-------
	flipped list
	"""
	to_return = [None]*len(vec)
	for i in range(len(vec)):
		to_return[i] = height - vec[i]
	return to_return

def csv_to_kdt(csv_filepath, img_height):
	""" Fit reference spot coordinates to a k-d tree

	Parameters
	----------
	csv_filepath : string filepath to csv file containing reference points
	img_height : height of image

	Returns
	-------
	ref_kdt : sklearn.neighbors.kd_tree.KDTree object containing reference points 
				y-coordinates are flipped about img_height 
	"""
	ref_df = pd.read_csv(csv_filepath)
	ref_points = ref_df.loc[:, ['col', 'row']].as_matrix()

	for i in range(len(ref_points)):
		point = ref_points[i]
		first_elem = point[0]
		second_elem = img_height - point[1]
		point = np.array([first_elem, second_elem])
		ref_points[i] = point

	ref_kdt = KDTree(ref_points, leaf_size=2, metric='euclidean')	# kdt is a kd tree with all the reference points
	return ref_kdt

"""
Pair scores
"""

def get_pair_scores(df):
	""" Calculate pair scores for each pair of workers in df.

	Parameters
	----------
	df : pandas dataframe

	Returns
	-------
	pair_scores : pandas dataframe
		indices and columns of the dataframe are worker IDs
		contents are pair scores
		pair score between worker_A and worker_B = ((avg A->B NND) + (avg B->A NND))/2
	"""

	worker_list = get_workers(df)
	pair_scores = pd.DataFrame(index = worker_list, columns = worker_list)
	for worker in worker_list:
		worker_df = slice_by_worker(df, worker)
		worker_coords = get_click_properties(worker_df)[:,:2]
		worker_kdt = KDTree(worker_coords, leaf_size=2, metric='euclidean')

		for other_worker in worker_list:
			if worker == other_worker:
				pair_scores[worker][other_worker] = 0
				continue

			other_worker_df = slice_by_worker(df, other_worker)
			other_worker_coords = get_click_properties(other_worker_df)[:,:2]
			other_worker_kdt = KDTree(other_worker_coords, leaf_size=2, metric='euclidean')

			list_A = [None]*len(worker_coords)
			for i in range(len(worker_coords)):
				dist, ind = other_worker_kdt.query([worker_coords[i]], k=1)
				list_A[i] = dist[0][0]

			list_B = [None]*len(other_worker_coords)
			for j in range(len(other_worker_coords)):
				dist, ind = worker_kdt.query([other_worker_coords[j]], k=1)
				list_B[j] = dist[0][0]

			pair_scores[worker][other_worker] = (np.mean(list_A) + np.mean(list_B))/2

	return pair_scores

def get_worker_pair_scores(df):
	""" Calculate the total pairwise score for each workers in df.

	Parameters
	----------
	df : pandas dataframe

	Returns
	-------
	worker_scores : pandas dataframe
		indices of the dataframe are worker IDs
		column header of dataframe is "score" 
		"score" is the sum of the worker's pairwise scores
	"""
	worker_list = get_workers(df)
	pair_scores = get_pair_scores(df)
	worker_scores = pd.DataFrame(index = worker_list, columns = ["score"])
	for worker in worker_list:
		worker_scores["score"][worker] = sum(pair_scores[worker].values)
	return worker_scores

def get_worker_pair_score_threshold(df):
	""" Calculate a pairwise score threshold for all workers in
	df using Otsu's method. Assumes a bimodal distribution.

	Parameters
	----------
	df : pandas dataframe

	Returns
	-------
	pairwise score threshold value
	"""
	worker_pairwise_scores = get_worker_pair_scores(df)	# score workers based on pairwise matching (this step does not use clusters)
	worker_scores_list = worker_pairwise_scores['score'].tolist()	# get IDs of all workers
	return filters.threshold_otsu(np.asarray(worker_scores_list))	# threshold otsu

def slice_by_worker_pair_score(df, threshold):
	""" Drop all annotations in df by workers with average pairwise 
	score greater than threshold

	Parameters
	----------
	df : pandas dataframe
	threshold : pairwise score threshold

	Returns
	-------
	df : pandas dataframe
	"""

	worker_pair_scores = get_worker_pair_scores(df)					# df with all workers. index = worker_ids, values = scores
	high_scores = worker_pair_scores[worker_pair_scores.score > threshold]	# df with only bad workers
	high_scoring_workers = high_scores.index.values
	for worker in high_scoring_workers:
		df = df[df.worker_id != worker]
	return df

"""
Sorting clusters by size and clumpiness
"""

def get_cluster_size_threshold(clusters):
	""" Calculate a cluster size threshold for all clusters
	using K-means in 1D. Assumes a bimodal distribution.

	Parameters
	----------
	clusters : pandas dataframe 
		(centroid_x | centroid_y | members)

	Returns
	-------
	cluster size threshold
	"""
	total_list = []
	for i in range(len(clusters.index)):
		row = clusters.iloc[[i]]
		members = row.iloc[0]['members']
		worker_list = [member[3] for member in members]
		num_members = len(np.unique(worker_list))
		total_list.append(num_members)
	total_array = np.asarray(total_list)
	km = KMeans(n_clusters = 2).fit(total_array.reshape(-1,1))
	cluster_centers = km.cluster_centers_
	return (cluster_centers[0][0]+cluster_centers[1][0])/2

def sort_clusters_by_size(clusters, threshold):
	""" Sort clusters by quantity of unique annotators.

	Parameters
	----------
	clusters : pandas dataframe 
		(centroid_x | centroid_y | members)
	threshold : threshold quantity of unique annotators

	Returns
	-------
	small_clusters : pandas dataframe containing clusters 
		for which num unique annotators < threshold
		(centroid_x | centroid_y | members)
	large_clusters : pandas dataframe containing clusters 
		for which num unique annotators >= threshold
		(centroid_x | centroid_y | members)
	"""
	small_clusters_list = []
	large_clusters_list = []
	for i in range(len(clusters.index)):
		row = clusters.iloc[[i]]
		members = row.iloc[0]['members']
		centroid_x = row.iloc[0]['centroid_x']
		centroid_y = row.iloc[0]['centroid_y']

		worker_list = []
		for member in members:
			worker_list.append(member[3])
		num_members = len(np.unique(worker_list))

		if (num_members < threshold):
			small_clusters_list.append([centroid_x, centroid_y, members])
		else:
			large_clusters_list.append([centroid_x, centroid_y, members])

	small_clusters = pd.DataFrame(index = range(len(small_clusters_list)), columns = ['centroid_x','centroid_y','members'])
	large_clusters = pd.DataFrame(index = range(len(large_clusters_list)), columns = ['centroid_x','centroid_y','members'])

	for i in range(len(small_clusters_list)):
		small_clusters['centroid_x'][i] = small_clusters_list[i][0]
		small_clusters['centroid_y'][i] = small_clusters_list[i][1]
		small_clusters['members'][i] = small_clusters_list[i][2]

	for i in range(len(large_clusters_list)):
		large_clusters['centroid_x'][i] = large_clusters_list[i][0]
		large_clusters['centroid_y'][i] = large_clusters_list[i][1]
		large_clusters['members'][i] = large_clusters_list[i][2]

	return small_clusters, large_clusters

def get_clumpiness_threshold(clusters, bin_size, cutoff_fraction):
	""" Calculate a clumpiness threshold for all clusters
	by finding the value between the tail and the main mode. 
	Assumes a left-skewed unimodal distribution.

	Protocol for finding threshold:
	Sort all clusters into bins.
		e.g. if bin_size = 0.1, then sort clusters into bins 100-95%, 95-85%, ..., 5-0% 
		(% of contributors contributed only once to this cluster)
	Find all values between two adjacent bins where the number of clusters in the higher-value 
		bin is at least cutoff_fraction times greater than the number of clusters in the lower-value bin, 
		and neither bin contains zero clusters.
	threshold is the lowest of these values minus 0.1 (in order to move one bin to the left, 
		to minimize the number of clusters which are actually single in the group of clusters 
		detected as clumpy), or 0 if no such values exist.

	Parameters
	----------
	clusters : pandas dataframe 
		(centroid_x | centroid_y | members)
	bin_size : see protocol
	cutoff_fraction : see protocol

	Returns
	-------
	clumpiness threshold
	"""
	single_fraction_list = []
	for i in range(len(clusters.index)):
		row = clusters.iloc[[i]]
		members = row.iloc[0]['members']
		x_coords = []
		y_coords = []
		workers = []
		for member in members:
			x_coords.append(member[0])
			y_coords.append(member[1])
			workers.append(member[3])

		# Calculate replication of unique workers for each cluster
		unique_workers = np.unique(workers)
		num_instances_list = []
		for unique_worker in unique_workers:
			num_instances_list.append(workers.count(unique_worker))
		singles = num_instances_list.count(1)
		single_fraction = singles/len(unique_workers)
		single_fraction_list.append(single_fraction)

	(n, bins, patches) = plt.hist(single_fraction_list, bins=np.arange(0, 1+2*bin_size, bin_size) - bin_size/2)
	total_counts_reversed = list(reversed(n))

	threshold = 0
	prev_count = 0
	for i in range(len(total_counts_reversed)):
		count = total_counts_reversed[i]
		if (count != 0):
			if((count < prev_count/cutoff_fraction) and (count != 0) and (prev_count != 0)):
				threshold = 1 - i*bin_size - bin_size/2
		prev_count = count
	return threshold

def sort_clusters_by_clumpiness(clusters, threshold):
	""" Sort clusters by fraction of contributors who contribute once
	to the cluster.

	Parameters
	----------
	clusters : pandas dataframe 
		(centroid_x | centroid_y | members)
	threshold : threshold fraction of contributors who only contribute once

	Returns
	-------
	clumpy_clusters : pandas dataframe containing clusters 
		for which fraction of contributors who only contribute once < threshold
		(centroid_x | centroid_y | members)
	nonclumpy_clusters : pandas dataframe containing clusters 
		for which fraction of contributors who only contribute once >= threshold
		(centroid_x | centroid_y | members)
	"""
	clumpy_clusters_list = []
	nonclumpy_clusters_list = []
	clumpy_counter = 0
	nonclumpy_counter = 0
	for j in range(len(clusters.index)):
		row = clusters.iloc[[j]]
		members = row.iloc[0]['members']
		centroid_x = row.iloc[0]['centroid_x']
		centroid_y = row.iloc[0]['centroid_y']

		workers = []
		for member in members:
			workers.append(member[3])
		unique_workers = np.unique(workers)

		num_instances_list = []
		for unique_worker in unique_workers:
			num_instances_list.append(workers.count(unique_worker))
		singles = num_instances_list.count(1)
		single_fraction = singles/len(unique_workers)

		if (single_fraction < threshold):
			clumpy_clusters_list.append([centroid_x, centroid_y, members])
			clumpy_counter += 1
		else:
			nonclumpy_clusters_list.append([centroid_x, centroid_y, members])
			nonclumpy_counter += 1

	clumpy_clusters = pd.DataFrame(index = range(clumpy_counter), columns = ['centroid_x','centroid_y','members'])
	nonclumpy_clusters = pd.DataFrame(index = range(nonclumpy_counter), columns = ['centroid_x','centroid_y','members'])

	for k in range(clumpy_counter):
		clumpy_clusters['centroid_x'][k] = clumpy_clusters_list[k][0]
		clumpy_clusters['centroid_y'][k] = clumpy_clusters_list[k][1]
		clumpy_clusters['members'][k] = clumpy_clusters_list[k][2]

	for m in range(nonclumpy_counter):
		nonclumpy_clusters['centroid_x'][m] = nonclumpy_clusters_list[m][0]
		nonclumpy_clusters['centroid_y'][m] = nonclumpy_clusters_list[m][1]
		nonclumpy_clusters['members'][m] = nonclumpy_clusters_list[m][2]

	return clumpy_clusters, nonclumpy_clusters

"""
Getting click properties
"""

def get_time_per_click(df):
	""" Get time spent on each annotation.

	Parameters
	----------
	df : pandas dataframe 
		(timestamp | x | y | annotation_type | height | width image_filename | time_when_completed | worker_id)

	Returns
	-------
	time_spent_list : list of the amount of time spent on all clicks in df
		except the first click (fencepost)
		len(time_spent_list) = num rows in df
		time_spent_list[0] = None
		units are miliseconds
	"""
	timestamps = get_timestamps(df)
	time_spent_list = [None]*len(timestamps)
	for i in range (1,len(timestamps)):
		x = timestamps[i] - timestamps[i-1]
		time_spent_list[i] = x[0]
	return time_spent_list

def get_nnd_per_click(df, ref_kdt):
	""" Get the distance to the nearest neighbor (found in
		the k-d tree of reference points).

	Parameters
	----------
	df : pandas dataframe 
		(timestamp | x | y | annotation_type | height | width image_filename | time_when_completed | worker_id)

	Returns
	-------
	list of distances to the nearest neighbor (found in
		the k-d tree of reference points)
	"""
	coords = get_click_properties(df)[:,:2]
	dist, ind = ref_kdt.query(coords, k=1)
	dist_list = dist.tolist()
	return [dist[0] for dist in dist_list]

def get_avg_time_per_click(df, uid):
	""" Get the average amount of time that a worker spent on one click.

	Parameters
	----------
	df : pandas dataframe 
		(timestamp | x | y | annotation_type | height | width image_filename | time_when_completed | worker_id)
	uid : string worker ID

	Returns
	-------
	the average time that the worker spent per click
	"""		

	worker_timestamps = get_timestamps(df, uid)
	time_spent = max(worker_timestamps) - min(worker_timestamps)
	num_clicks = len(worker_timestamps)
	return time_spent[0]/num_clicks

"""
Cluster manipulation and analysis
"""

def get_cluster_means(clusters):
	""" Get the mean x and y of each cluster.
	(Different from cluster centroids, which are the exemplar
	annotation for each cluster.)

	Parameters
	----------
	clusters : pandas dataframe 
		(centroid_x | centroid_y | members)

	Returns
	-------
	numpy array of coords
	"""
	mean_coords = []
	for i in range(len(clusters.index)):
		row = clusters.iloc[[i]]
		members = row.iloc[0]['members']
		x_coords = []
		y_coords = []
		for member in members:
			x_coords.append(member[0])
			y_coords.append(member[1])
		mean_coord = [np.mean(x_coords), np.mean(y_coords)]
		mean_coords.append(mean_coord)
	return np.asarray(mean_coords)

def centroid_and_ref_df(clusters, csv_filepath, img_height):
	""" Assemble a dataframe of centroids found with annotation and reference data consolidated.
	
	Parameters
	----------
	df : Pandas Dataframe with annotation data (should already be cropped)
	clusters : pandas dataframe (centroid_x | centroid_y | members) ~ output of get_clusters()
		centroid_x = x coord of cluster centroid
		centroid_y = y coord of cluster centroid
		members = list of annotations belonging to the cluster
			each member is a list of properties of the annotation 
			i.e. [x coord, y coord, time spent, worker ID]
	csv_filepath : contains reference data

	Returns
	-------
	this dataframe: centroid_x | centroid_y | x of nearest ref | y of nearest ref | NN_dist | members
		* (the index is the Cluster ID)
		centroid_x = x coord of cluster centroid
		centroid_y = y coord of cluster centroid
		NN_x = x coord of nearest neighbor reference
		NN_y = y coord of nearest neighbor reference
		NN_dist = distance from centroid to nearest neighbor reference
		members = list of annotations belonging to cluster
			each annotation is a list of click properties: x_coord | y_coord | time_spent | worker_ID
	"""

	ref_kdt = csv_to_kdt(csv_filepath, img_height)
	ref_array = np.asarray(ref_kdt.data)

	centroid_IDs = range(clusters.shape[0])
	column_names = ['centroid_x', 'centroid_y', 'NN_x', 'NN_y', 'NN_dist', 'members']
	to_return = pd.DataFrame(index = centroid_IDs, columns = column_names)

	for i in centroid_IDs:

		to_return['centroid_x'][i] = clusters['centroid_x'][i]
		to_return['centroid_y'][i] = clusters['centroid_y'][i]

		coords = [[to_return['centroid_x'][i], to_return['centroid_y'][i]]]

		dist, ind = ref_kdt.query(coords, k=1)
		index = ind[0][0]
		nearest_neighbor = ref_array[index]

		to_return['NN_x'][i] = nearest_neighbor[0]
		to_return['NN_y'][i] = nearest_neighbor[1]
		to_return['NN_dist'][i] = dist[0][0]
		to_return['members'][i] = clusters['members'][i]		

	return to_return

def get_cluster_correctness(df, correctness_threshold):
	""" Assemble a dataframe of centroids found with annotation and reference data consolidated.
	
	Parameters
	----------
	centroid_and_ref_df : outputted by centroid_and_ref_df()
		centroid_x | centroid_y | x of nearest ref | y of nearest ref | NN_dist | members (x | y | time_spent | worker_id)
		* the index is the Centroid ID
	correctness_threshold : tolerance for correctness in pixels, None if correctness will not be visualized
		for each centroid, if NN_dist <= threshold, centroid is "correct"

	Returns
	-------
	2-column array with a row for each centroid
		column 0 = Centroid ID
		column 1 = True if centroid is "correct", False if centroid is "incorrect"
	"""

	num_centroids = df.shape[0]
	to_return = np.empty([num_centroids, 2])
	for i in range(num_centroids):
		to_return[i] = i
		NN_dist = df['NN_dist'][i]
		if (NN_dist <= correctness_threshold):
			to_return[i][1] = True
		else:
			to_return[i][1] = False
	return to_return

"""
Big plotters
"""

def plot_annotations(df, show_workers, show_correctness_workers, show_centroids, show_correctness_centroids, show_ref_points, show_NN_inc, centroid_and_ref_df, correctness_threshold, worker_marker_size, cluster_marker_size, img_filepath, csv_filepath, bigger_window_size):
	""" Quick visualization of worker annotations, clusters, and/or annotation and cluster "correctness." 
	
	Parameters
	----------
	df : pandas dataframe with annotation data for one crop only
	show_workers : bool whether to plot workers
	show_centroids : bool whether to plot cluster centroids
	show_ref_points : bool whether to plot reference annotations
	show_NN_inc : bool whether to show nearest neighbor for all "incorrect" centroids
	centroid_and_ref_df = pandas dataframe outputted by centroid_and_ref_df()
		centroid_x | centroid_y | x of nearest ref | y of nearest ref | NN_dist | members
	correctness_threshold : tolerance for correctness in pixels, None if correctness will not be visualized
	worker_marker_size, cluster_marker_size : plot parameters
	img_filepath, csv_filepath : paths to image and reference csv files
	bigger_window_size : bool whether to use bigger window size (for jupyter notebook)

	Returns
	-------
	none
	"""


	fig = plt.figure(figsize = (12,7))
	if bigger_window_size:
		fig = plt.figure(figsize=(14,12))

	handle_list = []
	img_height = df['height'].values[0]

	if correctness_threshold is not None:
		cluster_correctness = get_cluster_correctness(centroid_and_ref_df, correctness_threshold)

	if show_workers:
		if show_correctness_workers:
			member_lists = centroid_and_ref_df['members'].values
			for member_list, correctness in zip(member_lists, cluster_correctness):
				if correctness[1]:
					color = 'g'
				else:
					color = 'm'
				for member in member_list:
					coords = member[:2]
					plt.scatter([coords[0]], flip([coords[1]], img_height), s = worker_marker_size, facecolors = color, alpha = 0.5)
			handle_list.append(Line2D([0],[0], marker='o', color='w', markerfacecolor='g', label='anno of correct cluster'))
			handle_list.append(Line2D([0],[0], marker='o', color='w', markerfacecolor='m', label='anno of incorrect cluster'))
		else:
			worker_list = get_workers(df)
			for worker, color in zip(worker_list, colors):			# For each worker, use a different color.
				anno_one_worker = slice_by_worker(df, worker)		
				coords = get_click_properties(anno_one_worker)[:,:2]
				x_coords = coords[:,0]
				y_coords = coords[:,1]
				y_coords_flipped = flip(y_coords, img_height)
				handle = plt.scatter(x_coords, y_coords_flipped, s = worker_marker_size, facecolors = color, alpha = 0.5, label = worker)
				handle_list.append(handle)
		if not show_centroids:
			plt.title('Worker Annotations')	

	if show_centroids:
		x_coords = centroid_and_ref_df['centroid_x'].values
		y_coords = centroid_and_ref_df['centroid_y'].values
		y_coords_flipped = flip(y_coords, img_height)
		color_index = 0		
		if show_correctness_centroids:
			for i in range(len(centroid_and_ref_df.index)):		
				if (cluster_correctness[i][1]):
					color = 'g'								
				else:
					if show_NN_inc:
						color = colors[color_index]							
						color_index = (color_index+1)%len(colors)
						plt.scatter([centroid_and_ref_df['NN_x'].values[i]], [img_height-centroid_and_ref_df['NN_y'].values[i]], s = worker_marker_size*2, facecolors = color, edgecolors = color)
					else:
						color = 'm'
				plt.scatter(x_coords[i], y_coords_flipped[i], s = cluster_marker_size, facecolors = 'none', edgecolors = color)					
			handle_list.append(Line2D([0],[0], marker='o', color='w', markerfacecolor=None, markeredgecolor='g', label='centroid of correct cluster'))
			handle_list.append(Line2D([0],[0], marker='o', color='w', markerfacecolor=None, markeredgecolor='m', label='centroid of incorrect cluster'))
		else:
			plt.scatter(x_coords, y_coords_flipped, s = cluster_marker_size, facecolors = 'none', edgecolors = 'cyan')
			handle_list.append(Line2D([0],[0], marker='o', color='w', markerfacecolor=None, markeredgecolor='cyan', label='cluster centroid'))
		if not show_workers:
			plt.title('Cluster Centroids')

	if show_workers and show_centroids:
		plt.title('Worker Annotations and Cluster Centroids')

	if show_ref_points:
		ref_df = pd.read_csv(csv_filepath)								
		ref_points = ref_df.loc[:, ['col', 'row']].as_matrix()
		for point in ref_points:													
			plt.scatter([point[0]], [point[1]], s = 20, facecolors = 'y')
		handle_list.append(Line2D([0],[0], marker='o', color='w', markerfacecolor='y', label='reference points'))
	
	img = mpimg.imread(img_filepath)
	plt.imshow(img, cmap = 'gray')
	plt.legend(handles = handle_list, loc = 9, bbox_to_anchor = (1.2, 1.015))	
	plt.show()


