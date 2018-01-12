var config = require('config.json');
var _ = require('lodash');
var jwt = require('jsonwebtoken');
var Q = require('q');
var mongo = require('mongoskin');
var db = mongo.db(config.connectionString, { native_parser: true });
db.bind('attendance');

var service = {};

service.attendancerpt = attendancerpt;
service.get_Report = get_Report;

module.exports = service;

function attendancerpt(attendanceParam) {
    var deferred = Q.defer();

    // validation
    db.attendance.find(
        { employeeId: attendanceParam.employee_id },
        function (err, attend) {
            if (err) deferred.reject(err.name + ': ' + err.message);

            if (attend) {
                // Employee Id exists
                console.log('Employee Id "' + attendanceParam.employee_id + '" exists');
                get_Report(attendanceParam);
            } else {
                deferred.reject('Employee Id"' + attendanceParam.employee_id  + '" not found');
            }
        });
}

function get_Report(attendanceParam) {
    var deferred = Q.defer();

    db.attendance.find({employeeId: attendanceParam.employee_id }, function (err, attend) {
        if (err) deferred.reject(err.name + ': ' + err.message);

        if (attend) {
            // return required fields 
            deferred.resolve(_.pick(attend, 'Employee_Details.attendance.bucket.Month','Employee_Details.attendance.bucket.Total Leave',
            	'Employee_Details.attendance.bucket.Toatal Half Days',''));
        } else {
            // user not found
            deferred.resolve();
        }
    });

    return deferred.promise;
}

