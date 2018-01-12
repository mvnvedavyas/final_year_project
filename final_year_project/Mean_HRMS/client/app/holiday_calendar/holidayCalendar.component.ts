import { Component, OnInit} from '@angular/core';
import { User } from '../_models/index';
import { UserService } from '../_services/index';
import { Router,ActivatedRoute, Params } from '@angular/router';
import { AppConfig } from '../app.config';
import { Holiday } from '../_models/index';
import { HolidayService } from '../_services/index';
import { IMyDpOptions } from 'mydatepicker';

@Component({
	moduleId: module.id,
	selector: 'holiday-Calendar',
	templateUrl: 'holidayCalendar.component.html'
})

export class holidayCalendarComponent implements OnInit{
	model: any = {};
    loading = false;
	currentUser:User;
	holiday : Holiday;
	holidays: Holiday[] = [];
	constructor(private route: ActivatedRoute, private router: Router, private userService: UserService, private config: AppConfig, private holidayService: HolidayService) {
		this.currentUser = JSON.parse(localStorage.getItem('currentUser'));
		this.holiday = JSON.parse(localStorage.getItem('holiday'));
	}

	private myDatePickerOptions: IMyDpOptions = {
        // other options...
        dateFormat: 'dd.mm.yyyy'
       	
    };

    ngOnInit()
    {
    	this.loadAllHolidays();
    }

    private loadAllHolidays() {
        this.holidayService.getAll().subscribe(holidays => { this.holidays = holidays; });
    }

    public clear(): void {
    this.model.date_of_holiday = void 0;
	this.model.name_of_Holiday = undefined;
	}

    save(){
		this.loading = true;
		console.log(this.model);
		console.log(this.model);    
        this.holidayService.create(this.model)
		.subscribe(
			data => {
				location.reload();
			},
			error => {
				this.loading = false;
			}
		);
	}

    private jwt() {
			// create authorization header with jwt token
			let currentUser = JSON.parse(localStorage.getItem('currentUser'));
			if (currentUser && currentUser.token) {
				return 'Bearer ' + currentUser.token;
		}
	}
}
