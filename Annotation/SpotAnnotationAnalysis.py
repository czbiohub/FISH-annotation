""" This module contains the SpotAnnotationAnalysis class.
"""

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
from numpy import genfromtxt
import pandas as pd
import scipy
import sklearn as skl
from sklearn.cluster import AffinityPropagation
from sklearn import metrics

from sklearn.neighbors import KDTree

from QuantiusAnnotation import QuantiusAnnotation
from BaseAnnotation import BaseAnnotation

# ------- #

class SpotAnnotationAnalysis():
	""" The SpotAnnotationAnalysis class provides tools for
	annotation analysis.
	SpotAnnotationAnalysis takes in a BaseAnnotation object as an 
	input and saves it as a property of the class.
	"""

	# list of clustering algs handled
	clustering_algs = ['AffinityPropagation']

	# list of colors used for plotting different turkers
	colors = ['#3399FF', '#CC33FF', '#FFFF00', '#FF33CC', 
    '#9966FF', '#009999', '#99E3FF', '#B88A00', 
    '#33FFCC', '#FF3366', '#F5B800', '#FF6633',
    '#FF9966', '#FF9ECE', '#CCFF33', '#FF667F',
    '#EB4E00', '#FFCC33', '#FF66CC', '#33CCFF', 
    '#ACFF07', '#667FFF', '#FF99FF', '#FF1F8F',
    '#9999FF', '#99FFCC', '#FF9999', '#91FFFF',
    '#8A00B8', '#91BBFF', '#FFB71C', '#FF1C76']

	"""
	Constructor takes in a BaseAnnotation object and saves it as 
	a property of the SpotAnnotationAnalysis class
	"""
	def __init__(self, ba_obj):
		self.ba = ba_obj
		self.clusters_done = []
		self.cluster_objects = []
		self.clusters_found = []

	def test_alg(self, df, clustering_params):

		# Score workers based on pairwise matching (this step does not use clusters)		
		worker_scores = self.get_worker_scores(df)

		# Naïvely cluster annotations
		naive_clusters = self.get_clusters(df, clustering_params)
 		
		# Score clusters based on
		# 	Scores/ratings of workers who contributed to that cluster
		# 	Number of workers who contributed to that cluster


    # Returns a dataframe with score for all workers in the inputted df.
    # For each worker, worker_score = sum(pair scores of that worker).
    # indices of dataframe are worker IDs
    # column header of dataframe is the worker_score 
	def get_worker_scores(self, df):
		worker_list = self.ba.get_workers(df)
		pair_scores = self.get_pair_scores(df)
		print(pair_scores)

		worker_scores = pd.DataFrame(index = worker_list, columns = ["score"])
		for worker in worker_list:
			print(worker)
			worker_pair_scores = pair_scores[worker].values
			print(worker_pair_scores)
			worker_score = sum(worker_pair_scores)
			worker_scores["score"][worker] = worker_score

		return worker_scores

    # returns a dataframe with pair scores for all pairs of workers the inputted df
    # indices and columns of the dataframe are worker IDs
	def get_pair_scores(self, df):

		worker_list = self.ba.get_workers(df)
		pair_scores = pd.DataFrame(index = worker_list, columns = worker_list)

		counter = 0
		print("Calculating score for:")

		for worker in worker_list:
			counter += 1
			print(worker, "(", counter, "/", len(worker_list), ")")

			worker_df = self.ba.slice_by_worker(df, worker)
			worker_coords = self.ba.get_click_properties(worker_df)[:,:2]
			worker_kdt = KDTree(worker_coords, leaf_size=2, metric='euclidean')

			for other_worker in worker_list:
				if worker == other_worker:
					pair_scores[worker][other_worker] = 0
					continue

				other_worker_df = self.ba.slice_by_worker(df, other_worker)
				other_worker_coords = self.ba.get_click_properties(other_worker_df)[:,:2]
				other_worker_kdt = KDTree(other_worker_coords, leaf_size=2, metric='euclidean')

				list_A = [None]*len(worker_coords)
				for i in range(len(worker_coords)):
					worker_coord = worker_coords[i]
					dist, ind = other_worker_kdt.query([worker_coord], k=1)
					nnd = dist[0][0]
					list_A[i] = nnd

				list_B = [None]*len(other_worker_coords)
				for j in range(len(other_worker_coords)):
					other_worker_coord = other_worker_coords[j]
					dist, ind = worker_kdt.query([other_worker_coord], k=1)
					nnd = dist[0][0]
					list_B[j] = nnd

				pair_score = (np.mean(list_A) + np.mean(list_B))/2
				pair_scores[worker][other_worker] = pair_score

		return pair_scores

	"""
	Inputs:
		string name of clustering alg to use
		pandas dataframe with annotation data (should already be cropped)
		list of clustering params for clustering alg
	Returns:
		this dataframe: centroid_x | centroid_y | members
			* (the index is the Cluster ID)
			centroid_x = x coord of cluster centroid
			centroid_y = y coord of cluster centroid
			members = list of annotations belonging to the cluster
				each annotation comes with properties of that annotation (coordinates, time spent, and worker ID)
	"""
	def get_clusters(self, df, clustering_params):

		clustering_alg = clustering_params[0]

		if (clustering_alg not in self.clustering_algs):
			raise ValueError('Invalid clustering algorithm name entered.')

		if (clustering_alg == 'AffinityPropagation'):											# If AffinityPropagation is selected:
			cluster_centroids_list = []																# Initialize a list of cluster centroids

			if(len(clustering_params) != 2):														# Check that there's only one clustering parameter
				raise ValueError('Please enter a list containing the preference parameter.')

			click_properties = self.ba.get_click_properties(df)
			coords = click_properties[:,:2]															# Get all the coordinates from the annotation dataframe (dissociated from timestamps)

			af = self.get_cluster_object(coords, clustering_params)

			cluster_centers_indices = af.cluster_centers_indices_									# Get the indices of the cluster centers (list)
			num_clusters = len(cluster_centers_indices)

			labels = af.labels_																		# Each point that was in coords now has a label saying which cluster it belongs to.

			cluster_members_lists = [None]*num_clusters
			for i in range(len(cluster_members_lists)):
				cluster_members_lists[i] = []

			for j in range(len(click_properties)):
				index = labels[j]
				cluster_members_lists[index].append(click_properties[j])

			for k in range(num_clusters):
				cluster_centers = coords[cluster_centers_indices[k]]	# np array
				cluster_centroids_list.append(cluster_centers)

		centroid_IDs = range(num_clusters)
		column_names = ['centroid_x', 'centroid_y', 'members']
		to_return = pd.DataFrame(index = centroid_IDs, columns = column_names)

		for i in range(num_clusters):
			to_return['centroid_x'][i] = cluster_centroids_list[i][0]
			to_return['centroid_y'][i] = cluster_centroids_list[i][1]
			to_return['members'][i] = cluster_members_lists[i]

		return to_return

	"""
	Checks to see whether the cluster object has already been generated
	for the given df and clustering parameters and returns or calculates
	appropriately.
	""" 
	def get_cluster_object(self, coords, clustering_params):

		if (clustering_params[0] == 'AffinityPropagation'):

			for i in range(len(self.clusters_done)):
				coords_done = self.clusters_done[i][0]
				clustering_params_done = self.clusters_done[i][1]
				if ((np.array_equal(coords, coords_done)) and clustering_params == clustering_params_done):
					return self.cluster_objects[i]

			af = AffinityPropagation(preference = clustering_params[1]).fit(coords)				
			self.clusters_done.append([coords, clustering_params])
			self.cluster_objects.append(af)

			return af

	"""
	Inputs:
		string name of clustering alg to use
		df with annotation data (should already be cropped)
		list of clustering params for clustering alg
		csv_filename (contains reference data)
		img_filename (the cropping)
	Returns:
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
	def anno_and_ref_to_df(self, df, clustering_params, csv_filename, img_filename):

		anno_one_crop = self.ba.slice_by_image(df, img_filename)	# Remove data from other croppings.
		clusters = self.get_clusters(anno_one_crop, clustering_params)
		img_height = anno_one_crop['height'].values[0]
		ref_kdt = self.csv_to_kdt(csv_filename, img_height)
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

	"""
	Inputs:
		df in this form: centroid_x | centroid_y | x of nearest ref | y of nearest ref | NN_dist | members (x | y | time_spent | worker_id)
			* the index is the Centroid ID
		int threshold
			for each centroid, if NN_dist <= threshold, centroid is "correct"
	Returns:
		2-column array with a row for each centroid
			column 0 = Centroid ID
			column 1 = True if centroid is "correct", False if centroid is "incorrect"
	"""
	def get_cluster_correctness(self, df, threshold):
		num_centroids = df.shape[0]
		to_return = np.empty([num_centroids, 2])
		for i in range(num_centroids):
			to_return[i] = i
			NN_dist = df['NN_dist'][i]
			if (NN_dist <= threshold):
				to_return[i][1] = True
			else:
				to_return[i][1] = False
		return to_return

	""" 
	Input:
		string name of csv file containing reference points, aka "ground truth" values
	Returns:
		k-d tree containing the same reference points flipped vertically
	"""
	def csv_to_kdt(self, csv_filename, img_height):

		ref_df = pd.read_csv(csv_filename)
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
	Inputs:
		df with annotation data
		k-d tree with reference points, aka "ground truth" values
		img_filename to crop to
	Returns:
		List containing one list for each worker.
			Each list is comprised of, for each of the worker's
			points, the distance to the nearest neighbor (found in
			the k-d tree of references).
	"""
	def calc_distances(self, df, ref_kdt, img_filename):

		anno_one_crop = self.ba.slice_by_image(df, img_filename)	# Remove data from other croppings.
		worker_list = self.ba.get_workers(anno_one_crop)

		to_return = []

		for worker in worker_list:			
			anno = self.ba.slice_by_worker(anno_one_crop, worker)	
			coords = self.ba.get_click_properties(anno)[:,:2]
			dist, ind = ref_kdt.query(coords, k=1)
			dist_list = dist.tolist()
			values = []
			for i in range(len(dist_list)):
				values.append(dist_list[i][0])
			to_return.append(values)
		return to_return

	"""
	Inputs:
		df with annotation data
		img_filename to crop to
	Returns:
		list containing one list for each worker with time spent on each click
	Notes:
		Time spent on click_k = timestamp_k - timestamp_(k-1)
		Starts at index 1 of returned list. (Length of times_spent is same as length of timestamps.)
		Will not get a time spent on the first click
	"""
	def calc_time_per_click(self, df, img_filename):

		anno_one_crop = self.ba.slice_by_image(df, img_filename)	# Remove data from other croppings.
		worker_list = self.ba.get_workers(anno_one_crop)

		to_return = []

		for worker in worker_list:
			timestamps = self.ba.get_timestamps(anno_one_crop, worker)
			times_spent = [None]*len(timestamps)
			for i in range (1,len(timestamps)):
				times_spent[i] = timestamps[i] - timestamps[i-1]
			to_return.append(times_spent)

		return to_return

	"""
	Quick visualization of worker annotations, clusters, and/or annotation and cluster "correctness." 

	Inputs:
		pandas df with annotation data
		string img_filename to crop to
		string csv_filename with reference data
		int size of worker marker
		int size of cluster centroid marker
		bool whether to plot reference annotations
		bool whether to plot workers
		bool whether to plot cluster centroids
		bool whether to color worker markers green/magenta to indicate "correctness"
		bool whether to color centroid markers green/magenta to indicate "correctness"
		bool whether to color an incorrect cluster's nearest neighbor the same color as the incorrect cluster
		int threshold distance from centroid to the nearest reference annotation beyond which the entire cluster is "incorrect"
		string name of clustering algorithm
		list of clustering parameters
		bool whether to use bigger window size (for jupyter notebook)
	Returns:
		none
	"""
	def plot_annotations(self, df, img_filename, csv_filename, worker_marker_size, cluster_marker_size, show_ref_points, show_workers, show_clusters, show_correctness_workers, show_correctness_clusters, show_NN_inc, correctness_threshold, clustering_params, bigger_window_size):
		if bigger_window_size:
			fig = plt.figure(figsize=(14,12))
		else:
			fig = plt.figure(figsize = (12,7))

		anno_one_crop = self.ba.slice_by_image(df, img_filename)	# Remove data from other croppings.
		worker_list = self.ba.get_workers(anno_one_crop)

		if show_clusters or show_correctness_workers:
			clusters = self.anno_and_ref_to_df(df, clustering_params, csv_filename, img_filename)
			member_lists = clusters['members'].values	# list of lists

			if correctness_threshold is not None:
				cluster_correctness = self.get_cluster_correctness(clusters, correctness_threshold)

		img_height = anno_one_crop['height'].values[0]

		if show_workers:

			if show_correctness_workers:
				for i in range(len(member_lists)):			# for every cluster
					members = member_lists[i]					# get the list of annotations (w/ click properties) in that cluster
					if (cluster_correctness[i][1]):
						color = 'g'						
					else:								
						color = 'm'
					for member in members:						# plot each annotation in that cluster
						coords = member[:2]
						plt.scatter([coords[0]], self.ba.flip([coords[1]], img_height), s = worker_marker_size, facecolors = color, alpha = 0.5)

			else:
				handle_list = []
				for worker, color in zip(worker_list, self.colors):			# For each worker, use a different color.
				    anno = self.ba.slice_by_worker(anno_one_crop, worker)		
				    coords = self.ba.get_click_properties(anno)[:,:2]
				    x_coords = coords[:,0]
				    y_coords = coords[:,1]
				    y_coords_flipped = self.ba.flip(y_coords, img_height)
				    handle = plt.scatter(x_coords, y_coords_flipped, s = worker_marker_size, facecolors = color, alpha = 0.5, label = worker)
				    handle_list.append(handle)
				plt.legend(handles = handle_list, loc = 9, bbox_to_anchor = (1.2, 1.015))

			if not show_clusters:
				plt.title('Worker Annotations')

		if show_clusters:

			x_coords = clusters['centroid_x'].values
			y_coords = clusters['centroid_y'].values
			y_coords_flipped = self.ba.flip(y_coords, img_height)

			color_index = 0		

			if show_correctness_clusters:
				for i in range(len(member_lists)):			# for every cluster
					if (cluster_correctness[i][1]):
						color = 'g'								
					else:
						if show_NN_inc:
							color = self.colors[color_index]							
							color_index = (color_index+1)%len(self.colors)
							plt.scatter([clusters['NN_x'].values[i]], [img_height-clusters['NN_y'].values[i]], s = worker_marker_size*2, facecolors = color, edgecolors = color)
						else:
							color = 'm'
					plt.scatter(x_coords[i], y_coords_flipped[i], s = cluster_marker_size, facecolors = 'none', edgecolors = color)					

			else:
				plt.scatter(x_coords, y_coords_flipped, s = cluster_marker_size, facecolors = 'none', edgecolors = '#ffffff')

			if not show_workers:
				plt.title('Cluster Centroids')

		if show_workers and show_clusters:
			plt.title('Worker Annotations and Cluster Centroids')

		if show_ref_points:
			ref_df = pd.read_csv(csv_filename)							# plot reference points			
			ref_points = ref_df.loc[:, ['col', 'row']].as_matrix()
			for point in ref_points:													
				plt.scatter([point[0]], [point[1]], s = 20, facecolors = 'y')
		img = mpimg.imread(img_filename)
		plt.imshow(img, cmap = 'gray')
		plt.show()


	"""
	Plots the average time spent per click for all workers 
	in the dataframe.

	Input:
		dataframe with annotation data
		bool whether to use a bigger window size (for jupyter notebook)
	Returns:
		none
	"""
	def plot_avg_time_per_click(self, df, bigger_window_size):
		avg_list = []
		for worker in self.ba.get_workers(df):
			avg_time = self.ba.get_avg_time_per_click(df, worker)
			avg_list.append(avg_time)
		n_bins = 10
		if bigger_window_size:
			fig = plt.figure(figsize=(14,12))
		else:
			fig = plt.figure(figsize = (12,7))
		plt.hist(avg_list, n_bins)
		plt.title('Average time spent per click')
		plt.xlabel('Time [ms]')
		plt.ylabel('Quantity of workers')
		plt.show()

	"""
	For each annotation (each click) in a dataframe, 
	plot nearest neighbor distance (nnd) vs. time spent. 
	Each point represents one annotation (one click). 
	All workers on one plot, colored by worker ID.
	Can color each point by correctness. 

	Implementation notes:
		if show_correctness
			can't use calc_time_per_click and calc_distances, because need
			to look at coordinates one by one and get time_spent on coordinate, 
			NND of associated centroid, and correctness of associated centroid.
		if not show_correctness, it's better to use calc_time_per_click and 
			calc_distances, which do not require clustering.

	Inputs:
		dataframe
		img_filename (the cropping)
		csv_filename (contains reference data)
		bool whether to color each point by correctness of cluster
		correctness_threshold
		clustering_params
	Returns:
		none
	"""
	def plot_nnd_vs_time_spent(self, df, img_filename, csv_filename, show_correctness, correctness_threshold, clustering_params):

		anno_one_crop = self.ba.slice_by_image(df, img_filename)	# Remove data from other croppings.
		fig = plt.figure(figsize = (10,7))
		img_height = anno_one_crop['height'].values[0]
		ref_kdt = self.csv_to_kdt(csv_filename, img_height)

		if show_correctness:

			# Goal: for each coordinate in coords, plot NND vs. time_spent and color with correctness
			# Run Af on all annotation coords (just once) and get labels (a list with a label for each annotation coordinate).
			# For each coordinate in coords:
			#		time_spent: pull from coords_with_times
			#		NND: query using a kdtree.
			#		correctness: index of coordinate is i=index of label. label[i] is index of correctness. correctness[index] is the appropriate correctness.
			#		aaaaand... plot NND vs. time_spent and color with correctness!

			coords = self.ba.get_click_properties(anno_one_crop)[:,:2]
			coords_with_times = self.ba.get_click_properties(anno_one_crop)[:,:3]
			clusters = self.anno_and_ref_to_df(df, clustering_params, csv_filename, img_filename)	# clusters -> NND, coordinates
			cluster_correctness = self.get_cluster_correctness(clusters, correctness_threshold)		# clusters <-> correctness
			af = self.get_cluster_object(coords, clustering_params)
			labels = af.labels_	

			for i in range(len(coords)):
				time_spent = coords_with_times[i][2]
				if(time_spent==0):
					continue
				coordinate = coords[i]		# a single coordinate
				dist, ind = ref_kdt.query([coordinate], k=1)
				NND = dist[0][0]
				index = labels[i]			# label[i] is the index of the cluster affiliated with this coordinate
				if(cluster_correctness[index][1]):
					color = 'g'
					marker_size = 4
					alpha_selection = 0.25
				else:
					color = 'm'
					marker_size = 20
					alpha_selection = 1
				plt.scatter([time_spent], [NND], s = marker_size, facecolors = color, edgecolors = None, alpha = alpha_selection)

		else:
			worker_list = self.ba.get_workers(anno_one_crop)
			time_list = self.calc_time_per_click(anno_one_crop, img_filename)		# list containing one list for each worker
			dist_list = self.calc_distances(anno_one_crop, ref_kdt, img_filename)	# list containing one list for each worker
			handle_list = []
			for i in range(len(worker_list)):			# for each worker
				color = self.colors[i]
				x_coords = time_list[i]
				y_coords = dist_list[i]
				handle = plt.scatter(x_coords, y_coords, s = 8, facecolors = color, alpha = 0.5, label = worker_list[i])
				handle_list.append(handle)
			plt.legend(handles = handle_list, loc = 9, bbox_to_anchor = (1.2, 1.015))
			plt.subplots_adjust(left=0.1, right=0.75)

		plt.title('Nearest Neighbor Distance (NND) vs. Time Spent For Each Click [ms]')
		plt.xlabel('Time Spent [ms]')
		plt.ylabel('Nearest Neighbor Distance (NND) [ms]')
		plt.show()

	"""
	For each annotation (each click) in a dataframe, 
	plot nearest neighbor distance (nnd) vs. worker index. 
	Each point represents one annotation (one click). 
	Can color each point by correctness. 

	Inputs:
		dataframe
		img_filename (the cropping)
		csv_filename (contains reference data)
		bool whether to color each point by correctness of cluster
		correctness_threshold
		clustering_params
	Returns:
		none
	"""
	def plot_nnd_vs_worker_index(self, df, img_filename, csv_filename, show_correctness, correctness_threshold, clustering_params, show_avgs):

		anno_one_crop = self.ba.slice_by_image(df, img_filename)	# Remove data from other croppings.
		worker_list = self.ba.get_workers(anno_one_crop)
		img_height = anno_one_crop['height'].values[0]
		ref_kdt = self.csv_to_kdt(csv_filename, img_height)
		dist_list = self.calc_distances(anno_one_crop, ref_kdt, img_filename)	# list containing one list for each worker

		fig = plt.figure(figsize = (10,7))

		# plot all clicks
		if show_correctness:
			click_properties = self.ba.get_click_properties(anno_one_crop)		
			coords = click_properties[:,:2]

			clusters = self.anno_and_ref_to_df(df, clustering_params, csv_filename, img_filename)	# clusters -> NND, coordinates
			cluster_correctness = self.get_cluster_correctness(clusters, correctness_threshold)		# clusters <-> correctness
			af = self.get_cluster_object(coords, clustering_params)
			labels = af.labels_	
			img_height = anno_one_crop['height'].values[0]
			ref_kdt = self.csv_to_kdt(csv_filename, img_height)

			for i in range(len(coords)):
				worker_id = click_properties[i][3]
				worker_index = np.where(worker_list == worker_id)

				coordinate = coords[i]
				dist, ind = ref_kdt.query([coordinate], k=1)
				NND = dist[0][0]
				index = labels[i]
				if(cluster_correctness[index][1]):
					color = 'g'
					marker_selection = 'o'
					marker_size = 4
					alpha_selection = 1
				else:
					color = 'm'
					marker_selection = '_'
					marker_size = 40
					alpha_selection = 1
				plt.scatter([worker_index], [NND], s = marker_size, facecolors = color, edgecolors = None, marker = marker_selection, alpha = alpha_selection)

		else:
			for i in range(len(worker_list)):			# for each worker
				x_coords = [i]*len(dist_list[i])
				y_coords = dist_list[i]
				plt.scatter(x_coords, y_coords, s = 4, alpha = 0.5, facecolors = 'c')

		# plot worker average distances
		if show_avgs:
			avg_distances = []
			for i in range(len(worker_list)):
				worker_distances = dist_list[i]
				worker_avg_dist = np.average(worker_distances)
				avg_distances.append(worker_avg_dist) 
			handle = plt.scatter(range(len(worker_list)), avg_distances, s = 60, facecolors = 'b', marker = '_', label = 'Average NND')
			plt.legend(handles = [handle], loc = 9, bbox_to_anchor = (1.15, 0.55))
			plt.subplots_adjust(left=0.1, right=0.8)

		plt.title('Nearest Neighbor Distance (NND) vs. Worker Index For Each Click')
		plt.xlabel('Worker Index')
		plt.ylabel('Nearest Neighbor Distance (NND)')
		plt.xticks(np.arange(0, len(worker_list), step=1))
		plt.show()

	"""
	For each annotation (each click) in a dataframe, 
	plot time spent on the click vs. worker index. 
	Each point represents one annotation (one click). 
	Can color each point by correctness. 

	Inputs:
		dataframe
		img_filename (the cropping)
		csv_filename
		bool whether to color each point by correctness of cluster
		correctness_threshold
		clustering_params
	Returns:
		none
	"""
	def plot_time_spent_vs_worker_index(self, df, img_filename, csv_filename, show_correctness, correctness_threshold, clustering_params, show_avgs):

		anno_one_crop = self.ba.slice_by_image(df, img_filename)			# Remove data from other croppings.
		worker_list = self.ba.get_workers(anno_one_crop)
		time_list = self.calc_time_per_click(anno_one_crop, img_filename)	# list containing one list for each worker

		fig = plt.figure(figsize = (10,7))

		# plot all clicks
		if show_correctness:
			click_properties = self.ba.get_click_properties(anno_one_crop)		# coordinates <-> time_spent
			coords = click_properties[:,:2]
			clusters = self.anno_and_ref_to_df(df, clustering_params, csv_filename, img_filename)	# clusters -> NND, coordinates
			cluster_correctness = self.get_cluster_correctness(clusters, correctness_threshold)		# clusters <-> correctness
			af = self.get_cluster_object(coords, clustering_params)
			labels = af.labels_	
			img_height = anno_one_crop['height'].values[0]
			ref_kdt = self.csv_to_kdt(csv_filename, img_height)

			for i in range(len(coords)):
				time_spent = click_properties[i][2]
				worker_id = click_properties[i][3]
				worker_index = np.where(worker_list == worker_id)

				coordinate = coords[i]
				dist, ind = ref_kdt.query([coordinate], k=1)
				index = labels[i]
				if(cluster_correctness[index][1]):
					color = 'g'
					marker_selection = 'o'
					marker_size = 10
					alpha_selection = 1
				else:
					color = 'm'
					marker_selection = '_'
					marker_size = 40
					alpha_selection = 1
				plt.scatter([worker_index], [time_spent], s = marker_size, facecolors = color, edgecolors = None, marker = marker_selection, alpha = alpha_selection)
		else:	
			for i in range(len(worker_list)):		# for each worker
				x_coords = [i]*len(time_list[i])
				y_coords = time_list[i]
				y_coords.pop(0)						# discard initial fencepost in time_list
				x_coords.pop(0)						# discard corresponding initial entry
				plt.scatter(x_coords, y_coords, s = 4, alpha = 0.5, facecolors = 'c')

		# plot worker average times
		if show_avgs:
			avg_times = []
			for i in range(len(worker_list)):
				worker_times = time_list[i]
				if not worker_times:				# if list of worker times is empty
					avg_times.append(0)
					continue
				worker_times.pop(0)
				worker_avg_time = np.average(worker_times)
				avg_times.append(worker_avg_time) 
			handle = plt.scatter(range(len(worker_list)), avg_times, s = 60, facecolors = 'b', marker = '_', label = 'Average time spent')
			plt.legend(handles = [handle], loc = 9, bbox_to_anchor = (1.15, 0.55))
			plt.subplots_adjust(left=0.1, right=0.8)

		plt.title('Time Spent [ms] vs. Worker Index')
		plt.xlabel('Worker Index')
		plt.ylabel('Time Spent [ms]')
		plt.xticks(np.arange(0, len(worker_list), step=1))
		plt.show()

	"""
	For each worker, plot total time spent vs. worker index. 
	Each bar represents one worker. 

	Inputs:
		dataframe
		img_filename (the cropping)
	Returns:
		none
	"""
	def plot_total_time_vs_worker_index(self, df, img_filename):

		anno_one_crop = self.ba.slice_by_image(df, img_filename)			# Remove data from other croppings.
		worker_list = self.ba.get_workers(anno_one_crop)

		fig = plt.figure(figsize = (10,7))

		handle_list = []
		for i in range(len(worker_list)):
			total_time = self.ba.get_total_time(anno_one_crop, worker_list[i])
			handle = plt.bar(i, total_time[0], color = self.colors[i], label = worker_list[i])
			handle_list.append(handle)

		plt.legend(handles = handle_list, loc = 9, bbox_to_anchor = (1.15, 1.015))
		plt.subplots_adjust(left=0.1, right=0.8)
		plt.title('Total Time Spent [ms] vs. Worker Index')
		plt.xlabel('Worker Index')
		plt.ylabel('Time Spent [ms]')
		plt.xticks(np.arange(0, len(worker_list), step=1))
		plt.show()

	"""
	For one worker in a dataframe,
	plot time spent on click vs. index of that click. 
	Each point represents one annotation (one click).

	Inputs:
		dataframe
		img_filename (the cropping)
		uid (worker ID)
	Returns:
		none
	"""
	def plot_time_spent_vs_click_index(self, df, img_filename, csv_filename, uid, show_correctness, correctness_threshold, clustering_params):

		anno_one_crop = self.ba.slice_by_image(df, img_filename)	# Remove data from other croppings.
		worker_list = self.ba.get_workers(anno_one_crop)
		fig = plt.figure(figsize = (10,7))
		anno_one_worker = self.ba.slice_by_worker(anno_one_crop, uid)

		if show_correctness:
			click_properties = self.ba.get_click_properties(anno_one_worker)		
			coords = click_properties[:,:2]
			clusters = self.anno_and_ref_to_df(df, clustering_params, csv_filename, img_filename)	# clusters -> NND, coordinates
			cluster_correctness = self.get_cluster_correctness(clusters, correctness_threshold)		# clusters <-> correctness
			af = self.get_cluster_object(coords, clustering_params)
			labels = af.labels_
			img_height = anno_one_worker['height'].values[0]
			ref_kdt = self.csv_to_kdt(csv_filename, img_height)
			num_clicks = len(coords)

			for i in range(num_clicks):
				time_spent = click_properties[i][2]
				click_index = i

				coordinate = coords[i]
				dist, ind = ref_kdt.query([coordinate], k=1)
				index = labels[i]
				if not isinstance(index, int):
					continue
				if(cluster_correctness[index][1]):
					color = 'g'
					marker_selection = 'o'
					marker_size = 10
					alpha_selection = 1
				else:
					color = 'm'
					marker_selection = 'o'
					marker_size = 40
					alpha_selection = 1
				plt.scatter([click_index], [time_spent], s = marker_size, facecolors = color, edgecolors = None, marker = marker_selection, alpha = alpha_selection)

		else:
			index = np.where(worker_list == uid)
			i = index[0][0]		# because np.where() returns a tuple containing an array
			time_list = self.calc_time_per_click(anno_one_crop, img_filename)	# list containing one list for each worker
			worker_time_list = time_list[i]
			num_clicks = len(worker_time_list)
			x_coords = range(num_clicks)
			y_coords = worker_time_list
			handle = plt.scatter(x_coords, y_coords, s = 4, facecolors = 'c', label = 'One click')
			plt.legend(handles = [handle], loc = 9, bbox_to_anchor = (1.15, 0.55))
			plt.subplots_adjust(left=0.1, right=0.8)
		
		plt.title('Time Spent [ms] vs. Click Index for Worker ' + uid)
		plt.xlabel('Click Index')
		plt.ylabel('Time Spent [ms]')
		plt.xticks(np.arange(0, num_clicks, step=10))
		plt.show()



