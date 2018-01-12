import { Component, OnInit} from '@angular/core';
import { User } from '../_models/index';
import { UserService } from '../_services/index';
import { Router, Params } from '@angular/router';
import { IMyDpOptions } from 'mydatepicker';

@Component({
	moduleId: module.id,
	selector: 'add-new-employee',
	templateUrl: 'addEmployee.component.html'
})

export class AddEmployeeComponent {
	currentUser:User;
	loading = false;
	
    model: any = {};
  	constructor(private router: Router, private userService: UserService) {
		this.currentUser = JSON.parse(localStorage.getItem('currentUser'));
		this.model.user_role = "Employee";
		this.model.admin_id = this.currentUser._id;
	}

	private myDatePickerOptions: IMyDpOptions = {
        // other options...
        dateFormat: 'dd-mm-yyyy',
       	
    };

    

	addNewEmployee() {
        this.loading = true;
		console.log(this.model);
		console.log(this.model);
        this.userService.create(this.model)
		.subscribe(
			data => {
				location.reload();
			},
			error => {
				this.loading = false;
			}
		);
	}
}