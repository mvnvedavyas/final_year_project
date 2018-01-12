var express = require('express');
var router = express.Router();
var holidayService = require('services/holiday.service');
var config = require('config.json');


//routes
router.get('/holidays', getAll);
router.post('/register', register);

module.exports = router;



function getAll(req, res) {
   holidayService.getAll()
       .then(function (holidays) {
           res.send(holdays);
       })
       .catch(function (err) {
           res.status(400).send(err);
       });
}

function register(req, res) {
   holidayService.create(req.body)
       .then(function () {
           res.sendStatus(200);
       })
       .catch(function (err) {
           res.status(400).send(err);
       });
}