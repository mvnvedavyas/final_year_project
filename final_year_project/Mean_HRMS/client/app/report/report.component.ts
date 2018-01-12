import { Component, OnInit} from '@angular/core';
import { Router,ActivatedRoute, Params } from '@angular/router';
import { AppConfig } from '../app.config';
import { User } from '../_models/index';
import { UserService } from '../_services/index';
import { Report } from '../_models/index';
import { ReportService } from '../_services/index';


@Component({
	moduleId: module.id,
	selector: 'report',
	templateUrl: 'report.component.html'
})

export class reportComponent {
	currentUser:User;
	selectedUser: User;
	id:string;
	report : Report[] = [];
	loading = false;
	model: any = {};

	constructor(private route: ActivatedRoute, private router: Router, private userService: UserService,private reportService:  ReportService) {
		this.currentUser = JSON.parse(localStorage.getItem('currentUser'));
	}

	private loadAllUsers() {
        this.reportService.get_report().subscribe(report => { this.report = report; });
    }

    months : string[] = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

    years : string[] = ["2013","2014","2015","2016","2017","2018","2019","2020","2021","2022","2023","2024","2025","2026","2027","2028","2029","2030","2031","2032","2033","2034","2035","2036","2037","2038","2039","2040","2041","2042","2043","2044","2045","2046","2047","2048","2049","2050","2051","2052","2053","2054","2055","2056","2057","2058","2059","2060"];

	get_info(){
		this.loading = true;
		console.log(this.model);
		console.log(this.model);    
        this.reportService.dataSend(this.model)
		.subscribe(	
			(data: any) => {
				location.reload();
			},
			(error: any) => {
				this.loading = false;
			}
		);
	}

	public clear(): void {
	this.model.choose_month = null;
	this.model.choose_year = null;
    this.model.employee_id = undefined;
	this.model.firstName = undefined;
	}

}