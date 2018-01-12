var config = require('config.json');
var express = require('express');
var router = express.Router();
var multer = require('multer');
var fs = require('fs');
var csv = require("fast-csv");
var Q = require('q');
var mongo = require('mongoskin');

var db = mongo.db(config.connectionString, { native_parser: true });
db.bind('attendance');

// routes
router.post('/uploadCSV', uploadCSV);


module.exports = router;

var uploadedFilename = "";
var monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

var storage = multer.diskStorage({ //multers disk storage settings
   destination: function (req, file, cb) {
       cb(null, './csvs/');
   },
  filename: function (req, file, cb) {
      var datetimestamp = Date.now();
       uploadedFilename = file.fieldname + '-' + datetimestamp + '.csv'
      cb(null, uploadedFilename);
   }
});

var upload = multer({ //multer settings
   storage: storage
}).single('file');

function uploadCSV(req, res) {
  upload(req,res,function(err){
       console.log(req.file);
       if(err){
           res.json({error_code:1,err_desc:err});
           return;
       }
       readCSV(uploadedFilename);
       res.json({error_code:0,err_desc:null});
  });
}


function readCSV(uploadedFilename){
   var stream = fs.createReadStream("./csvs/"+uploadedFilename);
   var result = [];
   var final = [];
   var dateRecords = [];
   var employeeID = "";
   var dateRecordsStarted = false;
   var month;
   var name;
   var halfDay=0;
   var totHours = 0;
   var deferred = Q.defer();
   csv.fromStream(stream, {ignoreEmpty: true})
   .on("data", function(data){
       if(data[0] == "EmpCode" && dateRecordsStarted == false){
         
           if(data[0] != null){
           employeeID = data[1];
            name = data[9];
           result = [];
           dateRecords = [];
           
       }
       } if ((data[0] == null || data[0] == "")&& data[6] != null ) {
           csv_month = data[6].substr(43);
           var arr = csv_month.split(" ");
           month = arr[0];
           year = arr[1];
       }
       else if(data[0] == "Date" && dateRecordsStarted == false){
           dateRecordsStarted = true;
       }
        else if(dateRecordsStarted == true){
   
       var date = data[0];
 
       var In = data[2];
       var Out = data[4]
       var Attendance = data[12];
       var hours = data[6];
       if(Attendance =="(P/2)"){
           halfDay ++;
       }
      if(Attendance != "Paid_Days  ="){
       dateRecords.push({bucket:{"Date":date, "In":In, "Out": Out, "Attendance": Attendance, "Hours worked ": hours}});
}
   if(Attendance == "Paid_Days  ="){
       var absent = data[9];
       var monthlyHours = data[6];
      dateRecords.push({bucket:{"Month: ":month,"Year: ":year ,"Total leave :": absent,"Total Half Days":halfDay, "Total hours (out of 180)":monthlyHours }});
   }
       if(data[0] == "Total For Employee :"){
           console.log("inside if");
           console.log(typeof result);
           dateRecordsStarted = false;
           result.push({employeeID:employeeID, attendance:dateRecords});
           final.push({"Name":name,"month":month,Employee_Details:result});
           db.attendance.insert(
          final,
          function (err, doc) {
              if (err) deferred.reject(err.name + ': ' + err.message);
              deferred.resolve();
          });
       }
           // //}
   
   }
})
   .on("end", function(){
      console.log("done");
   });
   
   
}