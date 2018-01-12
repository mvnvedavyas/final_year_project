import { Component, OnInit } from '@angular/core';
import { FileSelectDirective, FileDropDirective, FileUploader } from 'ng2-file-upload';
import { User } from '../_models/index';
import { UserService } from '../_services/index';
import { Router, ActivatedRoute, Params } from '@angular/router';
import { AppConfig } from '../app.config';
import { Http, Headers, RequestOptions, Response } from '@angular/http';


@Component({
	moduleId: module.id,
	selector: 'csv-upload',
	templateUrl: 'csv_upload.component.html'
})

export class CSVUploadComponent implements OnInit {
	
	
	currentUser:User;
	constructor(private route: ActivatedRoute, private router: Router, private userService: UserService, private config: AppConfig) {
		this.currentUser = JSON.parse(localStorage.getItem('currentUser'));
	}

	private jwt() {
			// create authorization header with jwt token
			let currentUser = JSON.parse(localStorage.getItem('currentUser'));
			if (currentUser && currentUser.token) {
				return 'Bearer ' + currentUser.token;
		}
	}
	
	public uploader:FileUploader = new FileUploader({url:'http://localhost:4000/upload/uploadCSV'})
	
	ngOnInit() {
       //override the onAfterAddingfile property of the uploader so it doesn't authenticate with //credentials.
       this.uploader.onAfterAddingFile = (file)=> { file.withCredentials = false; };
       //overide the onCompleteItem property of the uploader so we are 
       //able to deal with the server response.
       this.uploader.onCompleteItem = (item:any, response:any, status:any, headers:any) => {
            console.log("ImageUpload:uploaded:", item, status, response);
        };
    }
	
  	public hasBaseDropZoneOver:boolean = false;
  	public hasAnotherDropZoneOver:boolean = false;
	
 	
  	public fileOverBase(e:any):void {
  		  this.hasBaseDropZoneOver = e;
  	}
 
  	public fileOverAnother(e:any):void {
    	this.hasAnotherDropZoneOver = e;
  	}
}
