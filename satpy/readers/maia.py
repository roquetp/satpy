#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2017.
#
# Author(s):
#
#   Pascale Roquet <pascale.roquet@meteo.fr>
#
# This file is part of satpy.
#
# satpy is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# satpy is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# satpy.  If not, see <http://www.gnu.org/licenses/>.
"""Interface to CLAVR-X HDF4 products.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import h5py
import numpy as np

from satpy.dataset import Dataset, DatasetID
from satpy.readers.file_handlers import BaseFileHandler
from satpy.readers.hdf5_utils import HDF5FileHandler
from satpy.readers.yaml_reader import FileYAMLReader

logger = logging.getLogger(__name__)


CF_UNITS = {
    'none': '1',
}


class MAIAFileHandler(BaseFileHandler):
    sensors = {
        14: 'viirs',
        1: 'avhrr',  # TODO A CONTINUER
    }
    platforms = {
        'npp': 'npp',
    }
    rows_per_scan = {
        'viirs': 16,
        'avhrr': 1,
    }
    nadir_resolution = {
        'viirs': 742,
        'avhrr': 1050,
    }
    
    def __init__(self, filename, filename_info, filetype_info):
        super(MAIAFileHandler, self).__init__(
            filename, filename_info, filetype_info)
        self.selected = None
        self.read(filename)

    def read(self, filename):
        self.h5 = h5py.File(filename, 'r')
        missing = -9999.
        self.Lat = self.h5[u'DATA/Latitude'][:] / 10000.
        self.Lon = self.h5[u'DATA/Longitude'][:] / 10000.
        self.selected = (self.Lon > missing)
        self.file_content = {}
        for key in self.h5['DATA'].keys():
            self.file_content[key] = self.h5[u'DATA/' + key][:]
        for key in self.h5[u'HEADER'].keys():
            self.file_content[key] = self.h5[u'HEADER/' + key][:]
        self.h5.close()
        
        # Cloud Mask on pixel
        mask = 2**0+2**1+2**2
        lst =  self.file_content[u'CloudMask'][:]&mask
        lst = lst/2**0
        self.file_content[u"CM"] = lst
        
        # Cloud Mask confidence
        mask = 2**5+2**6
        lst = self.file_content[u'CloudMask'][:]&mask
        lst = lst/2**5
        self.file_content[u"CM_conf"] = lst
        
        Cloud Mask Quality
        mask = 2**3+2**4
        lst = self.file_content[u'CloudMask'][:]&mask
        lst = lst/2**3
        self.file_content[u'CM_qual'] = lst
        
        # Opaque Cloud
        mask =  2**21
        lst = self.file_content[u'CloudMask'][:]&mask
        lst = lst/2**21
        self.file_content[u'opaque_cloud'] = lst
      
        # land /water Background
        mask = 2**15+2**16+2**17
        lst = self.file_content[u'CloudMask'][:]&mask
        lst = lst/2**15
        self.file_content[u'land_water_background'] = lst
        
        # CT (Actual CloudType)
        mask = 2**4+2**5+2**6+2**7+2**8
        classif = self.file_content[u'CloudType'][:]&mask
        classif = classif/2**4
        self.file_content['CT'] = classif
        


    # def __getitem__(self, key):
    #     if key in self.file_content.keys():
    #         return self.file_content[key]
    #     else:
    #         return None
    #
    # def get_sensor(self, sensor):
    #     for k, v in self.sensors.items():
    #         if k in sensor:
    #             return v
    #     raise ValueError("Unknown sensor '{}'".format(sensor))
    #
    # def get_platform(self, platform):
    #     for k, v in self.platforms.items():
    #         if k in platform:
    #             return v
    #     return platform
    #
    # def get_rows_per_scan(self, sensor):
    #     for k, v in self.rows_per_scan.items():
    #         if sensor.startswith(k):
    #             return v
    #
    # def get_nadir_resolution(self, sensor):
    #     for k, v in self.nadir_resolution.items():
    #         if sensor.startswith(k):
    #             return v
    #     res = self.filename_info.get('resolution')
    #     if res.endswith('m'):
    #         return int(res[:-1])
    #     elif res is not None:
    #         return int(res)

    @property
    def start_time(self):
        return self.filename_info['start_time']

    @property
    def end_time(self):
        return self.filename_info.get('end_time', self.start_time)

    # def available_dataset_ids(self):
    #     """Automatically determine datasets provided by this file"""
    #     logger.debug("in available_dataset_ids ")
    #     sensor = self.get_sensor(self['sat_id'])
    #     nadir_resolution = self.get_nadir_resolution(sensor)
    #     for var_name, val in self.file_content.items():
    #         print var_name
    #         if isinstance(val, h5py.Dataset):
    #             ds_info = {
    #                 'file_type': self.filetype_info['file_type'],
    #                 'coordinates': ['Longitude', 'Latitude'],
    #                 'resolution': nadir_resolution,
    #
    #             }
    #             yield DatasetID(name=var_name, resolution=nadir_resolution), ds_info
    #
    # def get_shape(self, dataset_id, ds_info):
    #     logger.debug("in get_shape ")
    #     print dataset_id
    #     print ds_info
    #     var_name = dataset_id.name
    #     return self.file_content[var_name].shape
    #
    # def get_data_type(self, dataset_id, ds_info):
    #     base_default = super(MAIAFileHandler, self).get_data_type(
    #         dataset_id, ds_info)
    #     var_name = dataset_id.name
    #     return base_default
    #
    # def get_metadata(self, dataset_id, ds_info):
    #     logger.debug("in get_metadata %s", dataset_id.name)
    #     i = {}
    #     i.update(ds_info)
    #
    #     return i

    def get_dataset(self, key, info, out=None):
        #import pdb
        # pdb.set_trace()
        logger.debug("Reading %s.", key.name)
        values = self.file_content[key.name]
        if key.name in ("Latitude", "Longitude"):
            values = values / 10000.
        mask_values = np.ma.masked_array(values, mask=~self.selected)
#         import pdb
#         pdb.set_trace()
        ds = Dataset(mask_values, copy=False, **info)
        return ds





if __name__ == '__main__':
    pass
