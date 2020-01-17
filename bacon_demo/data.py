"""Module to generate datasets for tests and examples."""

import os
import csv
from collections import namedtuple
from datetime import datetime

from bacon.cubedef import CubeDef, Measure, AttributeLabel, AttributeMeasure
from bacon import cubedef


def sales_dataset():
	fn = os.path.dirname(__file__) + '/../data/Export Sales Info-demo.csv'
	f = csv.reader(open(fn))

	titles = [s.lower().replace(" ", "_") for s in next(f)]
	Record = namedtuple("SaleRecord", titles)

	def parse_string(s):
		return s or None

	def parse_int(s):
		return int(s) if s else None

	def parse_float(s):
		return float(s) if s else None

	def parse_datetime(s):
		return datetime.strptime(s, '%m/%d/%y %H:%M') if s else None

	def parse_date(s):
		return datetime.strptime(s, '%m/%d/%y').date() if s else None

	parsers = {
		'create_timestamp': parse_datetime,
		'edit_timestamp': parse_datetime,
		'merge_timestamp': parse_datetime,
		'probability': parse_int,
		'close_date': parse_date,
		'units': parse_int,
		'price': parse_float,
		'amount': parse_float,
		'creation_date': parse_date,
		'forecasted_units': parse_int,
		'forecasted_amount': parse_float}

	for row in f:
		yield Record(*map(
			lambda title_cell: parsers.get(title_cell[0], parse_string)(title_cell[1]),
			zip(titles, row)))


def sales_cubedef():
	cd = CubeDef()
	# Time hierarchy
	cd.add_label(cubedef.YearLabel('creation_date', dimension='Creation Date'))
	cd.add_label(cubedef.MonthLabel('creation_date', child_of='creation_date_year'))
	cd.add_label(cubedef.WeekLabel('creation_date', child_of='creation_date_year'))
	cd.add_label(cubedef.DayLabel('creation_date', child_of=['creation_date_month',
		'creation_date_week']))

	# Geographical dimension
	cd.add_label(AttributeLabel('state', dimension='location'))
	cd.add_label(AttributeLabel('city', child_of='state'))
	# cd.add_hierarchy('state', 'city')

	# Independent labels
	cd.add_label(AttributeLabel('status'))
	cd.add_label(AttributeLabel('sales_stage'))

	# Measures
	cd.add_measure(AttributeMeasure('units'))
	cd.add_measure(AttributeMeasure('forecasted_units'))
	cd.add_measure(Measure('amount',
		extract=lambda r: r.units * r.price,
		pretty=cubedef.pretty_from_format('%.02f')))
	cd.add_measure(Measure('forecasted_amount',
		extract=lambda r: r.forecasted_amount * r.price,
		pretty=cubedef.pretty_from_format('%.02f')))

	return cd
