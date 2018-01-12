var config = require('config.json');
var _ = require('lodash');
var jwt = require('jsonwebtoken');
var bcrypt = require('bcryptjs');
var Q = require('q');
var mongo = require('mongoskin');
var db = mongo.db(config.connectionString, { native_parser: true });
db.bind('holidays');

var service = {};

service.getAll = getAll;
service.create = create;

module.exports = service;
 
function getAll() {
   var deferred = Q.defer();

   db.holidays.find().toArray(function (err, holidays) {
       if (err) deferred.reject(err.name + ': ' + err.message);

       // return holidays
       holidays = _.map(holidays, function (holiday) {
           return holiday;
       });

       deferred.resolve(holidays);
   });

   return deferred.promise;
}

function create(holidayParam) {
   var deferred = Q.defer();

   // validation
   db.holidays.findOne(
       { date_of_holiday: holidayParam.date_of_holiday },
       function (err, holiday) {
           if (err) deferred.reject(err.name + ': ' + err.message);

           if (holiday) {
               // holidayname already exists
               deferred.reject('Date "' + holidayParam.date_of_holiday + '" is already taken');
           } else {
               createHoliday();
           }
       });

   function createHoliday() {
       // set user object to userParam without the cleartext password
      // var user = _.omit(userParam, 'password');
      var holiday = holidayParam;
      console.log(holiday);
       // add hashed password to user object
       //user.hash = bcrypt.hashSync(userParam.password, 10);
       
       db.holidays.insert(
           holiday,
           function (err, doc) {
               if (err) deferred.reject(err.name + ': ' + err.message);
               deferred.resolve();
           });
   }

   return deferred.promise;
}