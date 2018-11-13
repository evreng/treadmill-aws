from datetime import datetime, timedelta
from typing import Dict

from treadmill_aws.awscontext import GLOBAL

_CORES = {
    "medium": 2,
    "large": 2,
    "xlarge": 4,
    "2xlarge": 8,
    "4xlarge": 16,
    "10xlarge": 40,
    "12xlarge": 48,
    "16xlarge": 64,
    "24xlarge": 96,
}


def cores_of(instance_type):
    return _CORES[instance_type.split('.').pop()]


def get_latest_price(types, az):
    price_list = GLOBAL.ec2.describe_spot_price_history(
        InstanceTypes=types,
        AvailabilityZone=az,
        StartTime=datetime.now() - timedelta(days=1),
        EndTime=datetime.now(),
        ProductDescriptions=["Linux/UNIX"]).get('SpotPriceHistory')
    if price_list:
        return price_list


def get_pricing(instance_types, availability_zones):
    price_list = dict.fromkeys(availability_zones, {})
    for az in availability_zones:
        price_list[az] = dict.fromkeys(instance_types, {})
        for result in get_latest_price(instance_types, az):
            instance_type = result.get('InstanceType')
            price = float(result.get('SpotPrice'))
            core_price = price / cores_of(instance_type)
            price_list[az][instance_type] = {"price": price,
                                             "core_price":  core_price,
                                             "cores": cores_of(instance_type)}
    return price_list


def sort_by_price(pricing):
    choices = {}
    for az in pricing:
        for instance_type in pricing[az]:
            price = pricing[az][instance_type].get('core_price')
            if price not in choices:
                choices[price] = [(az, instance_type)]
            else:
                choices[price].append((az, instance_type))
    return choices


def sort_by_az(pricing):
    choices = {}
    for az in pricing:
        if az not in choices:
            choices[az] = []
        for instance_type in pricing[az]:
            price = pricing[az][instance_type].get('core_price')
            choices[az].append((instance_type, price))
        choices[az].sort(key=lambda k: k[1])
    return choices


def get_cheap_cores(cores, instance_types, azs, min_azs=3):
    pricing = get_pricing(instance_types, azs)
    price_list = sort_by_price(pricing)
    choices = []
    [choices.extend(price_list[price]) for price in sorted(price_list)]
    smallest = min([cores_of(itype) for itype in instance_types])
    cores_per_az, spare_cores = divmod(cores, smallest * min_azs)
    cores_per_az *= smallest
    result = {}  # type: Dict[str, int]
    left_cores = 0
    for az, instance_type in choices:
        if [choice for choice in result.keys() if az in choice]:
            continue
        if len(result) == min_azs:
            break
        choice = "{}|{}".format(az, instance_type)
        if choice not in result:
            result[choice] = 0
        left_cores += cores_per_az
        while left_cores >= cores_of(instance_type):
            left_cores -= cores_of(instance_type)
            result[choice] += 1
        spare_cores += left_cores
        if spare_cores and cores_of(instance_type) <= spare_cores:
            result[choice] += 1
            spare_cores -= cores_of(instance_type)
    return result