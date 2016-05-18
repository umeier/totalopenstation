# -*- coding: utf-8 -*-
# filename: formats/carlson_rw5.py
# Copyright 2014 Stefano Costa <steko@iosa.it>

# This file is part of Total Open Station.

# Total Open Station is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

# Total Open Station is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Total Open Station.  If not, see
# <http://www.gnu.org/licenses/>.

from totalopenstation.formats.conversion import horizontal_to_slope
from . import Feature
from .polar import Point, BasePoint, PolarPoint

# ussfeet = US Survey Feet
#
UNITS = {"angle": {"0": "dms", "1": "gon"},
         "distance": {"0": "feet", "1": "meter", "2": "ussfeet"}}


def _record(recstr):
    fields = recstr.split(',')
    record_fields = {f[0:2] : f[2:] for f in fields[1:]}

    # Record type, including comment records
    if len(fields[0]) > 2:
        record_fields['type'] = fields[0].strip('-')
        record_fields['comment'] = True
    else:
        record_fields['type'] = fields[0]

    # Note field
    try:
        record_fields['--']
    except KeyError:
        record_fields['note'] = ''
    else:
        record_fields['note'] = record_fields['--']
    return record_fields

class FormatParser:

    def __init__(self, data):
        self.rows = (r for r in data.splitlines() if not r.startswith('-- '))
        # Text comments, but not comment records ------------------------^

    def _points(self):
        points_coord = {}
        base_points = {}
        points = []
        pid = 0

        for row in self.rows:
            rec = _record(row)
            # Get angle and distance units
            if rec['type'] == 'MO':
                angle_unit = UNITS["angle"][rec['AU']]
                dist_unit = UNITS["distance"][rec['UN']]
            # Look for point coordinates
            if rec['type'] == 'SP':
                point_name = rec['PN']
                northing = float(rec['N '])  # extra whitespace
                easting = float(rec['E '])  # extra whitespace
                elevation = float(rec['EL'])
                point = Point(easting, northing, elevation)
                attrib = [rec['note']]
                f = Feature(point,
                            desc='PT',
                            id=pid,
                            point_name=point_name,
                            dist_unit=dist_unit,
                            attrib=attrib)
                points.append(f)
                pid += 1
                points_coord[point_name] = point
            # Look for station coordinates
            if rec['type'] == 'OC':
                station_name = rec['OP']
                northing = float(rec['N '])  # extra whitespace
                easting = float(rec['E '])  # extra whitespace
                elevation = float(rec['EL'])
                station_point = Point(easting, northing, elevation)
                points_coord[station_name] = station_point
                bp = BasePoint(x=easting, y=northing, z=elevation, ih=0)
                base_points[station_name] = bp
            # Look for line of sight values
            # Finalize station computing
            if rec['type'] == 'LS':
                ih = float(rec['HI'])
                th = float(rec['HR'])
                attrib = [rec['note']]
                try:
                    station_point
                except NameError:
                    station_point = Point(0, 0, 0)
                stf = Feature(station_point,
                              desc='ST',
                              id=pid,
                              point_name=station_name,
                              dist_unit=dist_unit,
                              attrib=attrib)
                bp = base_points[station_name]
                bp.ih = ih
                # Do not add station if previous station record is the same
                try:
                    last_stf
                except NameError:
                    last_stf = stf
                    points.append(stf)
                    pid += 1
                else:
                    if stf.point_name != last_stf.point_name or \
                                    stf.geometry.x != last_stf.geometry.x or \
                                    stf.geometry.y != last_stf.geometry.y or \
                                    stf.geometry.z != last_stf.geometry.z:
                        points.append(stf)
                        pid += 1
                        last_stf = stf
            # Look for polar data
            if rec['type'] in ('SS', 'TR', 'BD', 'BR', 'FD', 'FR'):
                point_name = rec['FP']
                attrib = [rec['note']]
                # Angle is recorded as azimuth or horizontal angle
                try:
                    azimuth = float(rec['AZ'])
                except KeyError:
                    azimuth = None
                # Angle is either Bearing, Angle Right or Left, Deflection Right or Left
                try:
                    angle = float(rec['BR'])
                except KeyError:
                    try:
                        angle = float(rec['AR'])
                    except KeyError:
                        try:
                            angle = float(rec['AL'])
                        except KeyError:
                            try:
                                angle = float(rec['DR'])
                            except KeyError:
                                try:
                                    angle = float(rec['DL'])
                                except KeyError:
                                    angle = None
                # Vertical angle is either Zenith, Vertical angle or Change elevation
                try:
                    z_angle = float(rec['ZE'])
                except KeyError:
                    try:
                        z_angle = float(rec['VA'])
                    except KeyError:
                        try:
                            z_angle = float(rec['CE'])
                        except KeyError:
                            z_angle = None
                try:
                    dist = float(rec['SD'])
                except KeyError:
                    try:
                        dist = float(rec['HD'])
                    except KeyError:
                        dist = None
                    else:
                        dist = horizontal_to_slope(dist, z_angle, angle_unit)
                attrib = [rec['note']]
                p = PolarPoint(angle_unit=angle_unit,
                               dist=dist,
                               angle=angle,
                               z_angle=z_angle,
                               th=th,
                               base_point=bp,
                               pid=pid,
                               text=point_name,
                               coordorder='NEZ')
                point = p.to_point()
                f = Feature(point,
                            desc='PT',
                            id=pid,
                            point_name=point_name,
                            dist_unit=dist_unit,
                            attrib=attrib)
                points.append(f)
                pid += 1
        return points

    def raw_line(self):
        '''Extract all Carlson RW5 data.

        Based on the "Tripod Data Systems, Inc. Raw Data Record Specification Survey Pro™ Version 3.6" document.

        Information needed are:
            - station :
            - backsight :
            - direct point :
            - computed point :

        Notes :
            - sometimes needed records are commented so it is needed to parse also comments

        Units are unchanged, format of the original parsed file

        TODO:
            - add all missing code
            - get comments
            - add the possibility to customize code
        '''

        points_coord = {}
        points = []
        pid = 0

        for row in self.rows:
            rec = _record(row)
            # Get angle and distance units
            if rec['type'] == 'MO':
                angle_unit = UNITS["angle"][rec['AU']]
                dist_unit = UNITS["distance"][rec['UN']]
            # Look for point coordinates
            if rec['type'] == 'SP':
                point_name = rec['PN']
                northing = float(rec['N '])  # extra whitespace
                easting = float(rec['E '])  # extra whitespace
                elevation = float(rec['EL'])
                point = Point(easting, northing, elevation)
                attrib = [rec['note']]
                f = Feature(point,
                            desc='PT',
                            id=pid,
                            point_name=point_name,
                            dist_unit=dist_unit,
                            attrib=attrib)
                points.append(f)
                pid += 1
                points_coord[point_name] = point
            # Look for station coordinates
            if rec['type'] == 'OC':
                station_name = rec['OP']
                northing = float(rec['N '])  # extra whitespace
                easting = float(rec['E '])  # extra whitespace
                elevation = float(rec['EL'])
                station_point = Point(easting, northing, elevation)
                points_coord[station_name] = station_point
            # Look for line of sight values
            # Finalize station computing
            if rec['type'] == 'LS':
                ih = float(rec['HI'])
                th = float(rec['HR'])
                attrib = [rec['note']]
                try:
                    station_point
                except NameError:
                    station_point = Point(0, 0, 0)
                stf = Feature(station_point,
                              desc='ST',
                              id=pid,
                              point_name=station_name,
                              angle_unit=angle_unit,
                              dist_unit=dist_unit,
                              ih=ih,
                              attrib=attrib)
                # Do not add station if previous station record is the same
                try:
                    last_stf
                except NameError:
                    last_stf = stf
                    points.append(stf)
                    pid += 1
                else:
                    if stf.point_name != last_stf.point_name or \
                                    stf.geometry.x != last_stf.geometry.x or \
                                    stf.geometry.y != last_stf.geometry.y or \
                                    stf.geometry.z != last_stf.geometry.z or \
                                    stf.properties['ih'] != last_stf.properties['ih']:
                        points.append(stf)
                        pid += 1
                        last_stf = stf
            # Look for back sight values
            if rec['type'] == 'BK':
                point_name = rec['BP']
                circle = rec['BC']
                try:
                    point = points_coord[point_name]
                except KeyError:
                    point = Point(0, 0, 0)
                f = Feature(point,
                            desc='BS',
                            id=pid,
                            point_name=point_name,
                            angle_unit=angle_unit,
                            circle=circle)
                points.append(f)
                pid += 1
            # Look for polar data
            if rec['type'] in ('SS', 'TR', 'BD', 'BR', 'FD', 'FR'):
                point_name = rec['FP']
                # Angle is recorded as azimuth or horizontal angle
                try:
                    azimuth = float(rec['AZ'])
                except KeyError:
                    azimuth = None
                # Angle is either Bearing, Angle Right or Left, Deflection Right or Left
                try:
                    angle = float(rec['BR'])
                except KeyError:
                    try:
                        angle = float(rec['AR'])
                    except KeyError:
                        try:
                            angle = float(rec['AL'])
                        except KeyError:
                            try:
                                angle = float(rec['DR'])
                            except KeyError:
                                try:
                                    angle = float(rec['DL'])
                                except KeyError:
                                    angle = None
                # Vertical angle is either Zenith, Vertical angle or Change elevation
                try:
                    z_angle = float(rec['ZE'])
                except KeyError:
                    try:
                        z_angle = float(rec['VA'])
                    except KeyError:
                        try:
                            z_angle = float(rec['CE'])
                        except KeyError:
                            z_angle = None
                try:
                    slope_dist = float(rec['SD'])
                except KeyError:
                    slope_dist = None
                try:
                    horizontal_dist = float(rec['HD'])
                except KeyError:
                    horizontal_dist = None
                attrib = [rec['note']]
                try:
                    point = points_coord[point_name]
                except KeyError:
                    point = Point(0, 0, 0)
                f = Feature(point,
                            desc='PO',
                            id=pid,
                            point_name=point_name,
                            angle_unit=angle_unit,
                            dist_unit=dist_unit,
                            azimuth=azimuth,
                            angle=angle,
                            z_angle=z_angle,
                            slope_dist=slope_dist,
                            horizontal_dist=horizontal_dist,
                            th=th,
                            attrib=attrib)
                points.append(f)
                pid += 1

        return points

    points = property(_points)
