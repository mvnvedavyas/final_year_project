import { Component, OnInit} from '@angular/core';
import { User } from '../_models/index';
import { UserService } from '../_services/index';
import { Router, ActivatedRoute, Params } from '@angular/router';

@Component({
	moduleId: module.id,
	templateUrl: 'Profileuser.component.html'
})

export class UserprofileComponent implements OnInit{
	currentUser:User;
	selectedUser: User;
	id:string;
	users: User[] = [];
    loading = false;
	
  	constructor(private route: ActivatedRoute, private router: Router, private userService: UserService) {
		this.currentUser = JSON.parse(localStorage.getItem('currentUser'));
	}
	ngOnInit() {
		this.userService.getById(this.route.snapshot.params['id']).subscribe(user => { this.selectedUser = user; });
    }
	
	private loadAllUsers() {
        this.userService.getAll().subscribe(users => { this.users = users; });
    }
	
	editUser(_id: string) {
		this.router.navigate(['/editUser',_id]);
	}

	deleteUser(_id: string) {
        this.userService.delete(_id).subscribe(() => { this.loadAllUsers() });
    }
	
	
}
