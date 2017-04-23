# -*- coding: cp1252 -*-
"""
Package for accessing the Priogrid online data API.

Karim Bahgat, 2015
"""

import os
import urllib2
import json
import datetime
import itertools

BASEURL = "http://grid.prio.org/api"

# INTERNAL RAW DATA

def available_cells():
    url = BASEURL + "/data/basegrid"
    raw = urllib2.urlopen(url).read()
    jdict = json.loads(raw)
    for giddict in jdict:
        yield giddict

def get_data(varid, startyr=None, endyr=None):
    url = BASEURL + "/data/" + str(varid)

    # options
    options = dict()

    # if not specified, get data for all years
    if not startyr: startyr = 1945
    if not endyr: endyr = datetime.date.today().year
    options["endYear"] = endyr
    options["startYear"] = startyr
    url += "?" + "&".join(("%s=%s" % keyval for keyval in options.items() ))
        
    # get
    raw = urllib2.urlopen(url).read()
    jdict = json.loads(raw)
    return jdict

# USER FUNCTIONS RETURNING USER FRIENDLY JSON DICTS

def available_variables():
    url = BASEURL + "/variables"
    raw = urllib2.urlopen(url).read()
    jdict = json.loads(raw)
    for vardict in jdict:
        yield vardict

def get_varinfo(name):
    url = BASEURL + "/variables/" + name
    raw = urllib2.urlopen(url).read()
    jdict = json.loads(raw)
    return jdict

def get_core_data(name):
    varinfo = get_varinfo(name)
    if varinfo["type"] == "core":
        data = get_data(varinfo["id"])
        giddict = dict([ (valuedict["gid"],{"data":valuedict["value"]})
                        for valuedict in data["cells"]
                        ])

        return giddict

    else:
        raise Exception("Could not find a core variable with that name")

def get_static_data(name):
    """
    Returns a dictionary with gid-valuedictionary mappings.
    Each valuedictionary contains a "data" entry, which references
    a single satic value.

    {
    192312: {"data": 43.2},
    192313: ...
    }
    """
    varinfo = get_varinfo(name)
    if varinfo["type"] == "static":
        data = get_data(varinfo["id"])
        giddict = dict([ (valuedict["gid"],{"data":valuedict["value"]})
                        for valuedict in data["cells"]
                        ])

        return giddict

    else:
        raise Exception("Could not find a static variable with that name")

def get_yearly_data(name, startyr=None, endyr=None, interpolated=False):
    """
    Returns a dictionary with gid-valuedictionary mappings.
    Each valuedictionary contains a "data" entry, which references
    a dictinoary of year-value mappings.

    {
    192312:
        {"data":
            {1980: 43.2, 1990: 98.1}
        }
    ,
    192313:
        ...
        ...
    }

    If interpolated is set to True, then variabels that miss values for some years
    will be linearly interpolated between known values. 
    """
    varinfo = get_varinfo(name)
    
    if varinfo["type"] == "yearly":
        data = get_data(varinfo["id"], startyr=startyr, endyr=endyr)
        giddict = dict()
        sorteddata = sorted(data["cells"], key=lambda vd: vd["gid"])
        for gid,valuedicts in itertools.groupby(sorteddata, key=lambda vd: vd["gid"]):
            yrdict = dict([(valuedict["year"],valuedict["value"])
                                    for valuedict in valuedicts
                                    ])
            info = {"data": yrdict}
            giddict[gid] = info

        if interpolated:
            def pairwise(iterable):
                a, b = itertools.tee(iterable)
                next(b, None)
                return zip(a, b)
            
            def lerp(factor, fromval, toval):
                valrange = toval - fromval
                return fromval + valrange * factor
            
            for gid,info in giddict.items():
                yrdict = info["data"]
                if len(yrdict) > 1:
                    for (fromyr,fromval),(toyr,toval) in pairwise(sorted(yrdict.items(),key=lambda i: i[0])):
                        curyr = fromyr + 1
                        interpneeded = fromval != toval
                        
                        while curyr != toyr:
                            if interpneeded:
                                factor = (curyr - fromyr) / float(toyr - fromyr)
                                yrdict[curyr] = lerp(factor, fromval, toval)
                            else:
                                yrdict[curyr] = fromval
                            curyr += 1

        return giddict

    else:
        raise Exception("Could not find a yearly variable with that name")

def get_unknown_data(name, **kwargs):
    """Gets any type of data, automatically detecting whether it is core, static, or yearly
    """
    varinfo = get_varinfo(name)
    if varinfo["type"] == "yearly":
        jdict = get_yearly_data(name, **kwargs)
    elif varinfo["type"] == "static":
        jdict = get_static_data(name)
    elif varinfo["type"] == "core":
        jdict = get_core_data(name)

    return jdict

##def assign_coords(giddict):
##    """
##    Given a dictionary containing gid ids as keys and dictionaries as values,
##    assign cell centerpoint lat long coordinates to each. 
##    """
##    lons = get_core_data("xcoord")
##    lats = get_core_data("ycoord")
##    for gid,valuedict in giddict.items():
##        valuedict["longitude"] = lons["data"]
##        valuedict["latitude"] = lats["data"]
##    return giddict




# MUCH BETTER AND MORE USER FRIENDLY CLASS INTERFACE



CACHED_VARS = dict()



class Variable(object):

    def __init__(self, name, startyr=None, endyr=None, interpolated=False):
        self.name = name
        self.startyr = startyr
        self.endyr = endyr
        self.interpolated = interpolated

    def __getattr__(self, attr):
        if "varinfo" not in CACHED_VARS[self.name]:
            CACHED_VARS[self.name]["varinfo"] = get_varinfo(self.name)
        return CACHED_VARS[self.name]["varinfo"][attr]

    def get(self, **cell):
        """Get this variable's value for a specified cell"""
        cellobj = Cell(**cell)
        if not cellobj.is_terrestial:
            raise Exception("Priogrid only has data for terrestial cells, you are trying to get data for a non-terrestial cell")

        if not self.name in CACHED_VARS:
            CACHED_VARS[self.name] = dict()
            CACHED_VARS[self.name]["data"] = get_unknown_data(self.name, startyr=self.startyr, endyr=self.endyr, interpolated=self.interpolated)

        # TODO: Test that doesnt slow down...
##        if not all((yr in CACHED_VARS[self.name]["data"][cellobj.gid]["data"] for yr in range(self.startyr, self.endyr+1))):
##            newdata = get_unknown_data(self.name, startyr=self.startyr, endyr=self.endyr, interpolated=self.interpolated)
##            yrdict = CACHED_VARS[self.name]["data"][cellobj.gid]["data"]
##            yrdict.update( newdata[cellobj.gid]["data"] )
                
        value = CACHED_VARS[self.name]["data"][cellobj.gid]["data"]
        return value



class Cell(object):
    centroid = "GeoJSON point"
    polygon = "GeoJSON polygon"
    bbox = "bbox tuple"

    def __init__(self, gid=None, xcoord=None, ycoord=None, col=None, row=None, **valuefilter):

        self.valuefilter = valuefilter
        
        # download all cell metadata
        if not "gid" in CACHED_VARS:
            CACHED_VARS["gid"] = [celldict["gid"] for celldict in available_cells()]

        
##        for corevar in ("xcoord","ycoord","col","row"):
##            if not corevar in CACHED_VARS:
##                CACHED_VARS[corevar] = dict()
##                CACHED_VARS[corevar]["data"] = get_core_data(corevar)

        # corevars currently dont work in online api
        # instead just calculate them manually
        # which is also faster and less download and memory expensive
            
        if gid != None:
            # first check that gid is valid
            if not isinstance(gid, int):
                raise Exception("Gid id must be of type int")
            if not 1 <= gid <= 259200:
                raise Exception("Gid id must range between 1 and 259200")
            
            self.gid = gid
            
            self.row = 1 + (gid-1) // 720
            self.col = gid - 720 * (self.row-1)
            self.xcoord = -180 + 0.25 + 0.5 * (self.col - 1)
            self.ycoord = -90 + 0.25 + 0.5 * (self.row - 1)

        elif xcoord != None and ycoord != None:
            # first check that coordinate is within world bounds
            if not -180 <= xcoord <= 180 or not -90 <= ycoord <= 90:
                raise Exception("Coordinates must have a valid longitude range between -180 and 180" \
                                + " and a valid latitude range between -90 and 90.")

            # since coords get rounded up, do a tiny offset down for coords at the maximum possible value
            if xcoord == 180: xcoord -= 0.01
            if ycoord == 90: ycoord -= 0.01
            
            # round to nearest half coord (ones on boundary between two cells get rounded up higher coord)
            xcoord = round((xcoord+0.25) * 2) / 2.0 - 0.25
            ycoord = round((ycoord+0.25) * 2) / 2.0 - 0.25
            
            self.xcoord = xcoord
            self.ycoord = ycoord

            # calculate row, col, and gid
            relx = (xcoord+0.25 + 180) / 360.0 # (offsets half a pixel)
            self.col = int(round(720 * relx))
            rely = (ycoord+0.25 + 90) / 180.0 # (offsets half a pixel)
            self.row = int(round(360 * rely))
            self.gid = 720 * (self.row-1) + self.col

        elif col != None and row != None:
            # first check that col row is within grid bounds
            if not 1 <= col <= 720 or not 1 <= row <= 360:
                raise Exception("Grid cell positions must have a valid column range between 1 and 720" \
                                + " and a valid row range between 1 and 360")
            
            self.col = col
            self.row = row

            # calculate x and y coord
            relx = (col-1) / 720.0
            rely = (row-1) / 360.0
            self.xcoord = -180 + 0.25 + 360 * relx
            self.ycoord = -90 + 0.25 + 180 * rely
            
            self.gid = 720 * (row-1) + col

    def __repr__(self):
        return "Cell instance(gid=%s, col=%s, row=%s, xcoord=%s, ycoord=%s)" % (self.gid,
                                                                                self.col,
                                                                                self.row,
                                                                                self.xcoord,
                                                                                self.ycoord,
                                                                                )

    @property
    def centroid(self):
        return {"type":"Point", "coordinates": (self.xcoord,self.ycoord)}

    @property
    def polygon(self):
        x,y = self.xcoord,self.ycoord
        return {"type":"Polygon", "coordinates": [[(x-0.25,y-0.25),
                                                   (x-0.25,y+0.25),
                                                   (x+0.25,y+0.25),
                                                   (x+0.25,y-0.25),
                                                   (x-0.25,y-0.25)]]
                }

    def get(self, name, **valuefilter):
        """Get this cell's value for a specified variable name"""
        if not valuefilter:
            valuefilter = self.valuefilter
        varobj = Variable(name, **valuefilter)
        value = varobj.get(gid=self.gid)
        return value

    @property
    def is_terrestial(self):
        return self.gid in CACHED_VARS["gid"]



class Grid(object):
    def __init__(self, startyr=None, endyr=None, interpolated=False):
        self.startyr = startyr
        self.endyr = endyr
        self.interpolated = interpolated

        if not "gid" in CACHED_VARS:
            CACHED_VARS["gid"] = [celldict["gid"] for celldict in available_cells()]
        self._gids = list(CACHED_VARS["gid"])

    def __iter__(self):
        for gid in self._gids:
            yield Cell(gid, startyr=self.startyr, endyr=self.endyr, interpolated=self.interpolated)

    def filtered(self, condition):
        """
        EXAMPLE:

        world = Grid(startyr=2014)
        africa = world.filtered(lambda c: c.get("gwno")[2014] > 400 and c.get("gwno")[2014] < 700)
        for cell in africa:
            print cell
        """
        for cell in self:
            if condition(cell):
                yield cell




# testing

if __name__ == "__main__":

    # view all varnames
    for varinfo in available_variables():
        print varinfo["name"]

    # view interpolated landuse years
    for gid,info in get_yearly_data("pop_hyd_sum", interpolated=True).items():
        for yr,val in sorted(info["data"].items(), key=lambda i: i[0]):
            print gid,yr,val

    # try assigning geoinfo/coords to retrieved data
    #assign_coords(get_static_data("forest_gc"))



