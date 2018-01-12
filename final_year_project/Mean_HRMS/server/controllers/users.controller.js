var config = require('config.json');
var express = require('express');
var router = express.Router();
var userService = require('services/user.service');
var attendancerptService = require('services/attendancerpt.service');

// routes
router.post('/authenticate', authenticate);
router.post('/register', register);
router.post('/report',report);
router.get('/get_report',getReport);
router.get('/', getAll);
router.options('/csvs', uploadFile);
router.get('/:_id', getById);
router.get('/current', getCurrent);
router.put('/:_id', update);
router.delete('/:_id', _delete);


module.exports = router;

function authenticate(req, res) {
    userService.authenticate(req.body.username, req.body.password)
        .then(function (user) {
            if (user) {
                // authentication successful
                res.send(user);
            } else {
                // authentication failed
                res.status(401).send('Username or password is incorrect');
            }
        })
        .catch(function (err) {
            res.status(400).send(err);
        });
}

function register(req, res) {
    userService.create(req.body)
        .then(function () {
            res.sendStatus(200);
        })
        .catch(function (err) {
            res.status(400).send(err);
        });
}

function report(req, res) {
    
    attendancerptService.attendancerpt(req.body)
        .then(function () {
            console.log("hi");
            res.sendStatus(200);
        })
        .catch(function (err) {
            res.status(400).send(err);
        });
}

function getReport(req, res) {
    attendanceService.get_Report(req.user.sub)
        .then(function (user) {
            if (user) {
                res.send(user);
            } else {
                res.sendStatus(404);
            }
        })
        .catch(function (err) {
            res.status(400).send(err);
        });
}

function getAll(req, res) {
    userService.getAll()
        .then(function (users) {
            res.send(users);
        })
        .catch(function (err) {
            res.status(400).send(err);
        });
}

function getCurrent(req, res) {
    userService.getById(req.user.sub)
        .then(function (user) {
            if (user) {
                res.send(user);
            } else {
                res.sendStatus(404);
            }
        })
        .catch(function (err) {
            res.status(400).send(err);
        });
}

function update(req, res) {
    userService.update(req.params._id, req.body)
        .then(function () {
            res.sendStatus(200);
        })
        .catch(function (err) {
            res.status(400).send(err);
        });
}

function _delete(req, res) {
    userService.delete(req.params._id)
        .then(function () {
            res.sendStatus(200);
        })
        .catch(function (err) {
            res.status(400).send(err);
        });
}

function getById(req, res) {
	console.log("Hi");
    userService.getById(req.params._id)
        .then(function (user) {
			console.log("user id  : " + user._id);
            res.send(user);
        })
        .catch(function (err) {
            res.status(400).send(err);
        });
}

function uploadFile(req, res){
	upload(req,res,function(err){
		console.log(req.file);
		if(err){
			 res.json({error_code:1,err_desc:err});
			 return;
		}
		 res.json({error_code:0,err_desc:null});
	});
}


 